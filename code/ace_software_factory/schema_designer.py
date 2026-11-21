"""Turunkan skema SQLite dari model domain dengan tipe dan relasi eksplisit.

Kolom kunci, bentuk literal default, dan foreign key diperiksa
sebelum SQL diterbitkan. Nama objek dikutip dan ekspresi pengguna
diterima hanya sebagai literal sesuai tipe. Keluaran memuat SQL,
jejak entitas, serta hash model yang dipakai.
"""
import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import ContractError, canonical, checked, decode, entries, identifier, identity, integer, obj, read, schema, text


TYPES = {"text": "TEXT", "integer": "INTEGER", "boolean": "INTEGER", "blob": "BLOB"}
ACTIONS = {"restrict":"RESTRICT", "cascade":"CASCADE", "set_null":"SET NULL", "no_action":"NO ACTION"}


def _quote(name):
    return f'"{name}"'


def _column_list(columns):
    return ", ".join(map(_quote, columns))


def _literal(value, kind, nullable):
    if value is None and nullable:
        return "NULL"
    if kind == "text" and isinstance(value,str) and len(value) <= 500 and "\x00" not in value:
        return "'"+value.replace("'", "''")+"'"
    if kind == "integer":
        return str(integer(value,"Default integer",-2**63,2**63-1))
    if kind == "boolean" and type(value) is bool:
        return str(int(value))
    raise ContractError("Literal default tidak cocok dengan tipe kolom.")


@dataclass(frozen=True)
class Column:
    key: str
    kind: str
    nullable: bool
    default_sql: str | None

    @classmethod
    def parse(cls, raw):
        obj(raw, ("name","kind","nullable","default"))
        key = identifier(raw["name"],"Nama kolom")
        kind = raw["kind"]
        if not isinstance(kind,str) or kind not in TYPES or type(raw["nullable"]) is not bool:
            raise ContractError("Tipe atau nullable kolom tidak sah.")
        nullable = raw["nullable"]
        value = raw["default"]
        if value is None:
            default = None
        else:
            obj(value,("literal",))
            default = _literal(value["literal"],kind,nullable)
        return cls(key,kind,nullable,default)

    def sql(self):
        terms = [_quote(self.key), TYPES[self.kind]]
        if not self.nullable:
            terms.append("NOT NULL")
        if self.default_sql is not None:
            terms.extend(("DEFAULT",self.default_sql))
        if self.kind == "boolean":
            terms.append(f"CHECK ({_quote(self.key)} IN (0, 1))")
        return " ".join(terms)


def _known(raw, table, *, minimum=1):
    keys = tuple(identifier(value,"Kolom kunci") for value in entries(raw,16,minimum=minimum))
    if len(set(keys)) != len(keys) or set(keys)-table.keys():
        raise ContractError("Kolom kunci tidak dikenal atau ganda.")
    return keys


@dataclass
class Entity:
    name: str
    source: str
    columns: dict
    primary: tuple
    unique: list
    foreign_raw: list
    indexes: list

    @classmethod
    def parse(cls, row):
        obj(row,("name","source_ref","columns","primary_key","unique","foreign_keys","indexes"))
        key=identifier(row["name"],"Nama entitas")
        if key.startswith("sqlite_"):
            raise ContractError("Nama entitas disediakan untuk SQLite.")
        source=text(row["source_ref"],"Rujukan entitas",200)
        columns={}
        for value in entries(row["columns"],128,minimum=1):
            column=Column.parse(value)
            if column.key in columns:
                raise ContractError("Nama kolom ganda.")
            columns[column.key]=column
        primary=_known(row["primary_key"],columns)
        if any(columns[name].nullable for name in primary):
            raise ContractError("Kunci primer tidak boleh nullable.")
        unique=[_known(item,columns) for item in entries(row["unique"],64)]
        if len(set(unique)) != len(unique) or primary in unique:
            raise ContractError("Kunci unik ganda.")
        indexes=[_known(value,columns) for value in entries(row["indexes"],64)]
        if len(set(indexes))!=len(indexes):
            raise ContractError("Indeks ganda pada entitas.")
        foreign=entries(row["foreign_keys"],64)
        return cls(key,source,columns,primary,unique,foreign,indexes)


def _relations(entity, tables):
    result=[]
    seen=set()
    for row in entity.foreign_raw:
        obj(row,("columns","target","target_columns","on_delete"))
        local=_known(row["columns"],entity.columns)
        name=identifier(row["target"],"Entitas tujuan")
        action=row["on_delete"]
        target=tables.get(name)
        if target is None or not isinstance(action,str) or action not in ACTIONS:
            raise ContractError("Tujuan relasi atau aturan penghapusan tak dikenal.")
        remote=_known(row["target_columns"],target.columns)
        if local in seen or remote not in [target.primary,*target.unique] or len(local)!=len(remote):
            raise ContractError("Foreign key perlu target unik serta jumlah kolom cocok.")
        if any(entity.columns[a].kind != target.columns[b].kind for a,b in zip(local,remote,strict=True)):
            raise ContractError("Tipe kolom di dua sisi foreign key berbeda.")
        if action == "set_null" and any(not entity.columns[key].nullable for key in local):
            raise ContractError("SET NULL membutuhkan kolom lokal nullable.")
        seen.add(local)
        result.append((local, name, remote, action))
    return result


def design(model, expected=None):
    schema(model,"ace.factory-relational-model.v1",("model_ref","entities"))
    if expected is not None:
        checked(model,expected)
    tables={}
    for row in entries(model["entities"],128,minimum=1):
        entry=Entity.parse(row)
        if entry.name in tables:
            raise ContractError("Entitas ganda.")
        tables[entry.name]=entry
    ddl=["PRAGMA foreign_keys = ON;","BEGIN IMMEDIATE;"]
    indexes=[]
    report=[]
    names=set(tables)
    for key, table in sorted(tables.items()):
        terms=[row.sql() for row in table.columns.values()]
        terms.append(f"PRIMARY KEY ({_column_list(table.primary)})")
        terms.extend(f"UNIQUE ({_column_list(group)})" for group in sorted(table.unique))
        links=_relations(table,tables)
        for local,target,remote,action in links:
            terms.append(f"FOREIGN KEY ({_column_list(local)}) REFERENCES {_quote(target)} "
                         f"({_column_list(remote)}) ON DELETE {ACTIONS[action]}")
        ddl.append(f"CREATE TABLE {_quote(key)} (\n  "+",\n  ".join(terms)+"\n) STRICT;")
        for index_cols in sorted(table.indexes):
            index_name="ix_"+sha256(canonical([key,index_cols])).hexdigest()[:24]
            if index_name in names:
                raise ContractError("Nama indeks bertabrakan.")
            names.add(index_name)
            indexes.append(f"CREATE INDEX {_quote(index_name)} ON {_quote(key)} ({_column_list(index_cols)});")
        report.append({"name":key,"source_ref":table.source,"primary_key":list(table.primary),
                       "columns":[{"name":column.key,"kind":column.kind,"nullable":column.nullable}
                                  for column in table.columns.values()],
                       "foreign_keys":[{"columns":list(a),"target":b,"target_columns":list(c),"on_delete":d}
                                       for a,b,c,d in links]})
    sql="\n".join([*ddl,*indexes,"COMMIT;",""])
    result={"schema":"ace.factory-sqlite-schema.v1","model_sha256":identity(model),
            "model_ref":text(model["model_ref"],"Rujukan model",200),"sql_sha256":sha256(sql.encode()).hexdigest(),
            "entities":report,"sql":sql}
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model",type=Path)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--sql",action="store_true")
    args=parser.parse_args(argv)
    try:
        report=design(decode(read(args.model)),args.expect_sha256)
        sys.stdout.buffer.write(report["sql"].encode() if args.sql else canonical(report)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
