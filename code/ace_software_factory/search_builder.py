"""Bangun indeks teks penuh SQLite FTS5 dari kumpulan dokumen tertambat.

Query literal membatasi jumlah token, memilih mode ALL atau ANY, dan
menghasilkan cuplikan dengan rujukan dokumen. Indeks diuji secara lokal
dan hanya dibuka dari byte yang cocok dengan hash yang diharapkan.
"""
import argparse
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
import sys
from unicodedata import normalize

from ._contracts import ContractError, canonical, checked, decode, digest, entries, identifier, integer, obj, read, schema, text


WORD = re.compile(r"[^\W_]+", re.UNICODE)
MAX_INDEX = 8_000_000
MAX_DOCUMENT_BYTES = 2_000_000


def _body(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw)>30_000:
        raise ContractError("Dokumen perlu body teks dalam batas.")
    if any(not (char.isprintable() or char in "\r\n\t") for char in raw):
        raise ContractError("Body dokumen berisi karakter kontrol.")
    return raw


def build(snapshot, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.factory-search-plan.v1", ("collection_id", "snapshot_sha256", "source_ref", "title_weight"))
    checked(snapshot, plan["snapshot_sha256"])
    schema(snapshot, "ace.factory-search-snapshot.v1", ("source_ref", "documents"))
    collection = identifier(plan["collection_id"], "Koleksi")
    source = text(plan["source_ref"], "Sumber indeks")
    snapshot_ref = text(snapshot["source_ref"], "Sumber dokumen")
    weight = integer(plan["title_weight"], "Bobot judul", 1, 20)
    docs = {}
    total = 0
    for row in entries(snapshot["documents"], 2500):
        obj(row, ("id", "title", "body", "group", "source_ref"))
        key = identifier(row["id"], "ID dokumen")
        if key in docs:
            raise ContractError("ID dokumen ganda.")
        title = text(row["title"], "Judul dokumen", 250)
        body = _body(row["body"])
        group = identifier(row["group"], "Kelompok dokumen")
        pointer = text(row["source_ref"], "Sumber dokumen", 250)
        total += len(body.encode()) + len(title.encode())
        if total > MAX_DOCUMENT_BYTES:
            raise ContractError("Anggaran byte dokumen terlampaui.")
        docs[key] = (key, title, body, group, pointer)
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript("""
            CREATE TABLE index_info(id TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL, title_weight INTEGER NOT NULL) STRICT;
            CREATE TABLE metadata(doc_id TEXT NOT NULL UNIQUE, category TEXT NOT NULL, source TEXT NOT NULL) STRICT;
            CREATE VIRTUAL TABLE docs USING fts5(title, body, tokenize='unicode61 remove_diacritics 2');
        """)
        connection.execute("INSERT INTO index_info VALUES (?,?,?)", (collection, plan["snapshot_sha256"], weight))
        for number, (key, title, body, group, pointer) in enumerate(sorted(docs.values()), 1):
            connection.execute("INSERT INTO metadata(rowid,doc_id,category,source) VALUES (?,?,?,?)", (number,key,group,pointer))
            connection.execute("INSERT INTO docs(rowid,title,body) VALUES (?,?,?)", (number,title,body))
        connection.execute("INSERT INTO docs(docs) VALUES ('integrity-check')")
        connection.commit()
        if connection.execute("PRAGMA page_count").fetchone()[0]*connection.execute("PRAGMA page_size").fetchone()[0] > MAX_INDEX:
            raise ContractError("Indeks melampaui anggaran.")
        data = connection.serialize()
    report = {"schema": "ace.factory-search-report.v1", "source_ref": source, "snapshot_ref": snapshot_ref,
              "plan_sha256": expected, "snapshot_sha256": plan["snapshot_sha256"], "documents": len(docs),
              "index_sha256": sha256(data).hexdigest(), "bytes": len(data), "collection_id": collection}
    return data, report


def _phrase(raw, mode):
    normalized = normalize("NFKC", text(raw, "Teks pencarian", 240))
    words = list(dict.fromkeys(WORD.findall(normalized)))
    if not 1<=len(words)<=12 or any(len(word)>50 for word in words):
        raise ContractError("Jumlah atau panjang token query di luar batas.")
    if mode not in ("all", "any"):
        raise ContractError("Mode query perlu all atau any.")
    joiner = " AND " if mode == "all" else " OR "
    return words, joiner.join(f'"{word}"' for word in words)


def query(data, expected, raw, *, mode="all", limit=20, group=None):
    if not isinstance(data, bytes) or len(data)>MAX_INDEX or sha256(data).hexdigest()!=digest(expected):
        raise ContractError("Byte indeks tidak cocok dengan anchor.")
    terms, expression = _phrase(raw, mode)
    limit = integer(limit, "Batas hasil", 1, 100)
    group = identifier(group, "Kelompok tersaring") if group is not None else None
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.deserialize(data)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        identity = connection.execute("SELECT id,snapshot_sha256,title_weight FROM index_info").fetchall()
        if len(identity)!=1:
            raise ContractError("Identitas indeks tidak unik.")
        collection, source, weight = identity[0]
        params = [integer(weight,"Bobot indeks",1,20), expression]
        statement = """SELECT metadata.doc_id,docs.title,metadata.source,metadata.category,
                       snippet(docs,1,'[',']',' … ',15),bm25(docs,?,1) AS score
                       FROM docs JOIN metadata ON docs.rowid=metadata.rowid WHERE docs MATCH ?"""
        if group is not None:
            statement += " AND metadata.category=?"
            params.append(group)
        statement += " ORDER BY score,metadata.doc_id LIMIT ?"
        params.append(limit)
        hits = [{"doc_id": key, "title": title, "source_ref": pointer, "group": lane,
                 "snippet": snippet, "score": rank} for key,title,pointer,lane,snippet,rank in connection.execute(statement,params)]
    return {"schema": "ace.factory-search-query.v1", "collection_id": collection, "index_sha256": expected,
            "snapshot_sha256": source, "terms": terms, "mode": mode, "group": group, "results": hits}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    index = actions.add_parser("build")
    for key in ("plan","snapshot","output"):
        index.add_argument(key,type=Path)
    index.add_argument("--expect-sha256",required=True)
    search = actions.add_parser("query")
    search.add_argument("index",type=Path)
    search.add_argument("words")
    search.add_argument("--mode", choices=("all","any"), default="all")
    search.add_argument("--group")
    search.add_argument("--limit",type=int,default=10)
    search.add_argument("--expect-sha256",required=True)
    args = parser.parse_args(argv)
    try:
        if args.action=="build":
            data, report=build(decode(read(args.snapshot)),decode(read(args.plan)),args.expect_sha256)
            with args.output.open("xb") as output:
                output.write(data)
        else:
            report=query(read(args.index,MAX_INDEX),args.expect_sha256,args.words,
                         mode=args.mode,limit=args.limit,group=args.group)
        sys.stdout.buffer.write(canonical(report)+b"\n")
    except (OSError,ValueError,RecursionError,sqlite3.Error) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
