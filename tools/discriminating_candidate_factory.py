"""Pabrik kandidat pembeda (discriminating) untuk corpus ACE (D9 — berkas baru).

Mengapa modul ini dibangun terpisah: evaluasi program menunjukkan korpus lama
terlalu mudah menjenuhkan *judge* sehingga gagal membedakan model kuat vs lemah.
Pabrik ini menghasilkan dua kelas episode berkendala keras secara deterministik:
1. `language`: tugas Bahasa Indonesia dengan TEPAT 5 kendala mekanis serentak
   (`word_count`, `sentence_count`, `required_phrases`, `forbidden_affix_roots`,
   dan `required_order`), diverifikasi terhadap jawaban kalibrasi internal
   lewat pemeriksa kendala resmi sebelum ditulis.
2. `code`: tugas Python dengan minimal 4 (bawaan 5) kendala keras serentak
   (tanda tangan fungsi persis, batas kompleksitas waktu/ruang, larangan modul/
   konstruksi pintasan via AST, kontrak keluaran + kasus tepi + docstring
   Bahasa Indonesia), turut diverifikasi AST + uji eksekusi atas solusi acuan.

Kandidat yang gagal pemeriksaan internal tidak pernah ditulis, keluaran JSONL
memakai skema persis `{id, kind, task_kind, instruction}` dengan ID berprefix unik,
bersifat deterministik untuk `seed` tetap, dan selalu menolak menimpa berkas lama.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Callable, Sequence

from tools.corpus_factory_lang import (
    DOMAIN_CONTEXT_TAGS,
    LANG_SCENARIOS,
    tokenize_words,
    split_sentences,
    verify_constraint_spec,
)
from tools.corpus_lint import load_frozen_prefixes


FACTORY_SCHEMA = "ace.discriminating-candidate-factory.v1"
DEFAULT_LANG_PREFIX = "D9L_"
DEFAULT_CODE_PREFIX = "D9C_"
LANGUAGE_CONSTRAINT_KEYS = (
    "word_count",
    "sentence_count",
    "required_phrases",
    "forbidden_affix_roots",
    "required_order",
)
CODE_CONSTRAINT_KEYS = (
    "exact_signature",
    "complexity_bound",
    "forbidden_constructs",
    "return_contract",
    "indonesian_docstring",
)
_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_-]+", re.UNICODE)


class DiscriminatingFactoryError(ValueError):
    """Galat konfigurasi atau ketidakcukupan kandidat yang lolos gerbang internal."""


@dataclass(frozen=True)
class CodeDiscriminatingSpec:
    family: str
    signature_name: str
    exact_signature: str
    complexity_bound: str
    forbidden_constructs: tuple[str, ...]
    return_contract: str
    indonesian_docstring_req: str
    lead_prompt: str
    edge_cases: tuple[str, ...]
    reference_code: str
    smoke_fn_source_checks: Callable[[dict[str, Any]], bool]


def _check_interval_merge(ns: dict[str, Any]) -> bool:
    fn = ns["gabung_jadwal_kritis"]
    assert fn([]) == []
    res = fn([(5, 8, "b"), (1, 5, "a"), (10, 12, "c"), (11, 14, "d")])
    assert res == [(1, 8, 2), (10, 14, 2)]
    try:
        fn([(9, 4, "bad")])
    except ValueError:
        return True
    return False


def _check_lru_quota(ns: dict[str, Any]) -> bool:
    fn = ns["ringkas_kuota_urut"]
    assert fn([], 3) == []
    out = fn([("b", 10), ("a", 5), ("b", 7), ("c", 1), ("a", 2)], 2)
    assert out == [("b", 17), ("a", 7)]
    try:
        fn([("x", 1)], 0)
    except ValueError:
        return True
    return False


def _check_shunting_eval(ns: dict[str, Any]) -> bool:
    fn = ns["hitung_ekspresi_linier"]
    assert fn("3 + 4 * 2 - (1 + 5)") == 5
    assert fn("20 // 3 + 7 % 4") == 9
    try:
        fn("10 / (2 - 2)")
    except ValueError:
        return True
    return False


def _check_dijkstra_bounded(ns: dict[str, Any]) -> bool:
    fn = ns["jalur_transit_terbatas"]
    edges = [("A", "B", 2), ("B", "C", 2), ("A", "C", 10)]
    assert fn(edges, "A", "C", 1) == (4, ["A", "B", "C"])
    assert fn(edges, "A", "C", 0) == (10, ["A", "C"])
    assert fn(edges, "A", "A", 0) == (0, ["A"])
    assert fn(edges, "A", "Z", 3) is None
    try:
        fn([("A", "B", -1)], "A", "B", 1)
    except ValueError:
        return True
    return False


def _check_sliding_window(ns: dict[str, Any]) -> bool:
    fn = ns["puncak_jendela_bergeser"]
    assert fn([4, 2, 7, 7, 1, 5], 3) == [7, 7, 7, 7]
    assert fn([1, 2], 5) == []
    try:
        fn([1, 2], 0)
    except ValueError:
        return True
    return False


def _check_topo_layers(ns: dict[str, Any]) -> bool:
    fn = ns["lapisan_topologis_stabil"]
    layers = fn({"build": ["lint", "test"], "test": ["lint"], "lint": [], "docs": []})
    assert layers == [["docs", "lint"], ["test"], ["build"]]
    assert fn({}) == []
    try:
        fn({"a": ["b"], "b": ["a"]})
    except ValueError:
        return True
    return False


CODE_SPECS: tuple[CodeDiscriminatingSpec, ...] = (
    CodeDiscriminatingSpec(
        family="interval_sweep_tiebreak",
        signature_name="gabung_jadwal_kritis",
        exact_signature="def gabung_jadwal_kritis(daftar_interval: list[tuple[int, int, str]]) -> list[tuple[int, int, int]]:",
        complexity_bound="O(n log n) waktu dan O(n) ruang",
        forbidden_constructs=("itertools", "heapq", "functools.cmp_to_key"),
        return_contract="Mengembalikan daftar terurut tuple (mulai, selesai, jumlah_interval_tergabung); tolak mulai > selesai dengan ValueError.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Gabungkan interval waktu yang saling bersinggungan atau bersentuhan ujung-ke-ujung dengan penghitungan densitas beban.",
        edge_cases=(
            "daftar kosong menghasilkan [] tanpa galat",
            "interval bersentuhan tepat (ujung_a == mulai_b) digabung menjadi satu blok",
            "interval mulai > selesai atau non-integer memicu ValueError eksplisit",
        ),
        reference_code='''def gabung_jadwal_kritis(daftar_interval: list[tuple[int, int, str]]) -> list[tuple[int, int, int]]:
    """Menggabungkan interval bersinggungan secara O(n log n) sekaligus menghitung jumlah blok asal."""
    if not daftar_interval:
        return []
    tersortir: list[tuple[int, int]] = []
    for item in daftar_interval:
        mulai, selesai, _ = item
        if isinstance(mulai, bool) or isinstance(selesai, bool) or not isinstance(mulai, int) or not isinstance(selesai, int):
            raise ValueError("Batas interval wajib integer.")
        if mulai > selesai:
            raise ValueError("Nilai mulai tidak boleh melampaui selesai.")
        tersortir.append((mulai, selesai))
    tersortir.sort()
    hasil: list[list[int]] = [[tersortir[0][0], tersortir[0][1], 1]]
    for mulai, selesai in tersortir[1:]:
        if mulai <= hasil[-1][1]:
            if selesai > hasil[-1][1]:
                hasil[-1][1] = selesai
            hasil[-1][2] += 1
        else:
            hasil.append([mulai, selesai, 1])
    return [(a, b, c) for a, b, c in hasil]
''',
        smoke_fn_source_checks=_check_interval_merge,
    ),
    CodeDiscriminatingSpec(
        family="deterministic_quota_topk",
        signature_name="ringkas_kuota_urut",
        exact_signature="def ringkas_kuota_urut(catatan: list[tuple[str, int]], batas_k: int) -> list[tuple[str, int]]:",
        complexity_bound="O(n log n) waktu dan O(u) ruang (u = jumlah kunci unik)",
        forbidden_constructs=("collections.Counter", "heapq", "sortedcontainers"),
        return_contract="Mengembalikan top-K pasangan (nama, total) urut total menurun lalu nama leksikografis menaik.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Agregasikan total pemakaian kuota per nama organ dari log transaksi lalu ambil K pemakai tertinggi dengan pemecahan seri leksikografis.",
        edge_cases=(
            "batas_k <= 0 atau bool atau bobot negatif memicu ValueError",
            "catatan kosong mengembalikan []",
            "skor total identik selalu diurutkan menaik berdasarkan nama string",
        ),
        reference_code='''def ringkas_kuota_urut(catatan: list[tuple[str, int]], batas_k: int) -> list[tuple[str, int]]:
    """Menjumlahkan catatan pemakaian kuota tanpa Counter dan memilih top-K secara deterministik."""
    if isinstance(batas_k, bool) or not isinstance(batas_k, int) or batas_k <= 0:
        raise ValueError("batas_k wajib bilangan bulat positif.")
    if not catatan:
        return []
    totals: dict[str, int] = {}
    for nama, jumlah in catatan:
        if not isinstance(nama, str) or not nama:
            raise ValueError("Nama entitas tidak valid.")
        if isinstance(jumlah, bool) or not isinstance(jumlah, int) or jumlah < 0:
            raise ValueError("Jumlah kuota wajib non-negatif.")
        totals[nama] = totals.get(nama, 0) + jumlah
    urut = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return urut[:batas_k]
''',
        smoke_fn_source_checks=_check_lru_quota,
    ),
    CodeDiscriminatingSpec(
        family="safe_arithmetic_shunting",
        signature_name="hitung_ekspresi_linier",
        exact_signature="def hitung_ekspresi_linier(ekspresi: str) -> int:",
        complexity_bound="O(n) waktu dan O(n) ruang",
        forbidden_constructs=("eval", "exec", "ast.literal_eval"),
        return_contract="Mengembalikan hasil int eksak ekspresi bertanda kurung (+, -, *, //, %); pembagian nol atau sintaks rusak memicu ValueError.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Tokenisasi dan evaluasi ekspresi bilangan bulat bertanda kurung dengan presedensi operator standar tanpa memakai evaluator bawaan.",
        edge_cases=(
            "operator tidak lengkap, kurung tak seimbang, atau pembagian nol memicu ValueError",
            "spasi berlebih di awal/tengah/akhir diabaikan",
            "presedensi *, //, % selalu lebih tinggi dari + dan -",
        ),
        reference_code='''def hitung_ekspresi_linier(ekspresi: str) -> int:
    """Mengevaluasi ekspresi aritmetika integer bertanda kurung memakai dua tumpukan deterministik."""
    if not isinstance(ekspresi, str) or not ekspresi.strip():
        raise ValueError("Ekspresi kosong.")
    tokens: list[str] = []
    i = 0
    n = len(ekspresi)
    while i < n:
        ch = ekspresi[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit():
            j = i
            while j < n and ekspresi[j].isdigit():
                j += 1
            tokens.append(ekspresi[i:j])
            i = j
        elif ekspresi.startswith("//", i):
            tokens.append("//")
            i += 2
        elif ch in "+-*%()":
            tokens.append(ch)
            i += 1
        else:
            raise ValueError(f"Karakter tidak dikenal: {ch!r}")
    prec = {"+": 1, "-": 1, "*": 2, "//": 2, "%": 2}
    vals: list[int] = []
    ops: list[str] = []

    def terapkan() -> None:
        if len(vals) < 2 or not ops:
            raise ValueError("Sintaks ekspresi tidak valid.")
        op = ops.pop()
        b = vals.pop()
        a = vals.pop()
        if op == "+":
            vals.append(a + b)
        elif op == "-":
            vals.append(a - b)
        elif op == "*":
            vals.append(a * b)
        elif op == "//":
            if b == 0:
                raise ValueError("Pembagian nol.")
            vals.append(a // b)
        elif op == "%":
            if b == 0:
                raise ValueError("Modulo nol.")
            vals.append(a % b)

    for tok in tokens:
        if tok.isdigit():
            vals.append(int(tok))
        elif tok == "(":
            ops.append(tok)
        elif tok == ")":
            while ops and ops[-1] != "(":
                terapkan()
            if not ops:
                raise ValueError("Kurung tidak seimbang.")
            ops.pop()
        else:
            while ops and ops[-1] != "(" and prec.get(ops[-1], 0) >= prec[tok]:
                terapkan()
            ops.append(tok)
    while ops:
        if ops[-1] == "(":
            raise ValueError("Kurung buka tidak tertutup.")
        terapkan()
    if len(vals) != 1:
        raise ValueError("Ekspresi gagal disederhanakan.")
    return vals[0]
''',
        smoke_fn_source_checks=_check_shunting_eval,
    ),
    CodeDiscriminatingSpec(
        family="bounded_shortest_transit",
        signature_name="jalur_transit_terbatas",
        exact_signature="def jalur_transit_terbatas(sisi: list[tuple[str, str, int]], asal: str, tujuan: str, maks_transit: int) -> tuple[int, list[str]] | None:",
        complexity_bound="O((K + 1) * E) waktu dan O(V) ruang (tanpa Dijkstra heapq)",
        forbidden_constructs=("heapq", "networkx", "sys.setrecursionlimit"),
        return_contract="Mengembalikan (biaya_minimum, daftar_simpul) atau None jika tak terjangkau; bobot atau maks_transit negatif memicu ValueError.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Cari rute biaya minimum dari simpul asal ke tujuan dalam batas maksimum simpul perantara pada graf berarah berbobot.",
        edge_cases=(
            "asal == tujuan mengembalikan (0, [asal]) pada batas transit >= 0",
            "tujuan tak terjangkau dalam batas transit mengembalikan None",
            "ikatan biaya total identik memilih rute berurutan leksikografis terkecil",
        ),
        reference_code='''def jalur_transit_terbatas(sisi: list[tuple[str, str, int]], asal: str, tujuan: str, maks_transit: int) -> tuple[int, list[str]] | None:
    """Menentukan rute biaya terendah berbatas transit memakai relaksasi Bellman-Ford lapis demi lapis."""
    if isinstance(maks_transit, bool) or not isinstance(maks_transit, int) or maks_transit < 0:
        raise ValueError("maks_transit wajib non-negatif.")
    for u, v, w in sisi:
        if isinstance(w, bool) or not isinstance(w, int) or w < 0:
            raise ValueError("Bobot sisi wajib integer non-negatif.")
    if asal == tujuan:
        return (0, [asal])
    best: dict[str, tuple[int, list[str]]] = {asal: (0, [asal])}
    for _ in range(maks_transit + 1):
        nxt = dict(best)
        for u, v, w in sisi:
            if u not in best:
                continue
            cand_cost = best[u][0] + w
            cand_path = best[u][1] + [v]
            if v not in nxt or (cand_cost, cand_path) < (nxt[v][0], nxt[v][1]):
                nxt[v] = (cand_cost, cand_path)
        best = nxt
    return best.get(tujuan)
''',
        smoke_fn_source_checks=_check_dijkstra_bounded,
    ),
    CodeDiscriminatingSpec(
        family="monotonic_deque_window",
        signature_name="puncak_jendela_bergeser",
        exact_signature="def puncak_jendela_bergeser(deret: list[int], ukuran_k: int) -> list[int]:",
        complexity_bound="O(n) waktu dan O(k) ruang memakai antrean dua-ujung monotonik",
        forbidden_constructs=("heapq", "numpy", "statistics"),
        return_contract="Mengembalikan list nilai maksimum tiap jendela valid panjang ukuran_k; ukuran_k <= 0 memicu ValueError.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Hitung nilai maksimum berjalan pada tiap posisi jendela geser ukuran tetap secara linear tanpa memindai ulang isi jendela.",
        edge_cases=(
            "deret kosong atau lebih pendek dari ukuran_k mengembalikan []",
            "ukuran_k <= 0 atau bool memicu ValueError",
            "nilai duplikat persis atau negatif tetap diproses tanpa meleset indeks kedaluwarsa",
        ),
        reference_code='''def puncak_jendela_bergeser(deret: list[int], ukuran_k: int) -> list[int]:
    """Menghitung maksimum jendela bergeser berbiaya O(n) memakai deque monotonik."""
    from collections import deque
    if isinstance(ukuran_k, bool) or not isinstance(ukuran_k, int) or ukuran_k <= 0:
        raise ValueError("ukuran_k wajib positif.")
    if len(deret) < ukuran_k:
        return []
    dq: deque[int] = deque()
    out: list[int] = []
    for idx, val in enumerate(deret):
        while dq and dq[0] <= idx - ukuran_k:
            dq.popleft()
        while dq and deret[dq[-1]] <= val:
            dq.pop()
        dq.append(idx)
        if idx >= ukuran_k - 1:
            out.append(deret[dq[0]])
    return out
''',
        smoke_fn_source_checks=_check_sliding_window,
    ),
    CodeDiscriminatingSpec(
        family="kahn_layered_tiebreak",
        signature_name="lapisan_topologis_stabil",
        exact_signature="def lapisan_topologis_stabil(ketergantungan: dict[str, list[str]]) -> list[list[str]]:",
        complexity_bound="O(V + E log V) waktu dan O(V + E) ruang (Kahn iteratif non-rekursif)",
        forbidden_constructs=("graphlib", "sys.setrecursionlimit", "functools.lru_cache"),
        return_contract="Mengembalikan daftar lapisan modul paralel terurut leksikografis per lapisan; siklus memicu ValueError.",
        indonesian_docstring_req="Wajib menyertakan docstring Bahasa Indonesia minimal 1 kalimat utuh.",
        lead_prompt="Susun jadwal lapis eksekusi paralel atas graf ketergantungan berarah beserta deteksi siklus memadai.",
        edge_cases=(
            "graf kosong {} mengembalikan []",
            "siklus dua simpul atau self-loop memicu ValueError",
            "prasyarat duplikat pada satu modul dihitung satu ketergantungan saja",
        ),
        reference_code='''def lapisan_topologis_stabil(ketergantungan: dict[str, list[str]]) -> list[list[str]]:
    """Menyusun lapisan eksekusi topologis Kahn yang deterministik tanpa rekursi."""
    if not ketergantungan:
        return []
    nodes: set[str] = set(ketergantungan.keys())
    for deps in ketergantungan.values():
        nodes.update(deps)
    indeg: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for mod, deps in ketergantungan.items():
        for dep in sorted(set(deps)):
            if dep == mod:
                raise ValueError(f"Self-loop pada modul {mod!r}.")
            adj[dep].append(mod)
            indeg[mod] += 1
    ready = sorted(n for n, d in indeg.items() if d == 0)
    layers: list[list[str]] = []
    visited = 0
    while ready:
        layers.append(ready)
        visited += len(ready)
        nxt: list[str] = []
        for u in ready:
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    nxt.append(v)
        ready = sorted(nxt)
    if visited != len(nodes):
        raise ValueError("Siklus ketergantungan terdeteksi.")
    return layers
''',
        smoke_fn_source_checks=_check_topo_layers,
    ),
)

_VARIANT_ANGLES: tuple[str, ...] = (
    "mode ketahanan kegagalan transaksi bertingkat",
    "mode audit presisi batas ekstrem",
    "mode sinkronisasi lintas zona waktu lokal",
    "mode deterministik bebas efek samping memori",
    "mode pemulihan masukan parsial tanpa mutasi",
    "mode antrean prioritas data terfragmentasi",
)


def verify_language_candidate_internal(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    """Gerbang internal fail-closed untuk kandidat bahasa: wajib TEPAT 5 kendala & lolos uji sampel."""
    reasons: list[str] = []
    spec = candidate.get("constraint_spec")
    sample = candidate.get("reference_answer")
    if not isinstance(spec, dict):
        return False, ["missing_constraint_spec"]

    active_keys = [
        k for k in LANGUAGE_CONSTRAINT_KEYS
        if spec.get(k) not in (None, {}, [], "")
    ]
    if len(active_keys) != 5:
        reasons.append(f"expected_5_constraints_got_{len(active_keys)}")
    if not isinstance(sample, str) or not sample.strip():
        reasons.append("empty_reference_answer")
        return False, reasons

    try:
        res = verify_constraint_spec(sample, spec)
    except Exception as exc:
        reasons.append(f"verify_exception:{exc}")
        return False, reasons

    if not res.get("passed"):
        failed = [k for k, v in res.get("checks", {}).items() if not v.get("passed")]
        reasons.append(f"sample_failed_checks:{failed}")

    instr = str(candidate.get("instruction", ""))
    for phrase in spec.get("required_phrases", []):
        if phrase not in instr:
            reasons.append(f"missing_phrase_in_instruction:{phrase}")
    for root in spec.get("forbidden_affix_roots", []):
        if root not in instr:
            reasons.append(f"missing_forbidden_root_in_instruction:{root}")

    return len(reasons) == 0, reasons


def _has_forbidden_ast_construct(source: str, forbidden: Sequence[str]) -> list[str]:
    tree = ast.parse(source)
    banned_set = set(forbidden)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in banned_set or alias.name.split(".")[0] in banned_set:
                    hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                full = f"{mod}.{alias.name}" if mod else alias.name
                if mod in banned_set or full in banned_set or mod.split(".")[0] in banned_set:
                    hits.append(full)
        elif isinstance(node, ast.Name) and node.id in banned_set:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute):
            parts: list[str] = []
            cur: Any = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                full = ".".join(reversed(parts))
                if full in banned_set:
                    hits.append(full)
    return hits


def verify_code_candidate_internal(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    """Gerbang internal fail-closed untuk kandidat kode: >=4 kendala keras + AST + uji solusi acuan."""
    reasons: list[str] = []
    spec = candidate.get("code_constraints")
    if not isinstance(spec, dict):
        return False, ["missing_code_constraints"]

    present_keys = [k for k in CODE_CONSTRAINT_KEYS if spec.get(k)]
    if len(present_keys) < 4:
        reasons.append(f"insufficient_hard_constraints:{len(present_keys)}")

    instr = str(candidate.get("instruction", ""))
    sig = str(spec.get("exact_signature", "")).strip()
    comp = str(spec.get("complexity_bound", "")).strip()
    ret = str(spec.get("return_contract", "")).strip()
    banned = tuple(spec.get("forbidden_constructs") or ())
    if not sig or sig not in instr:
        reasons.append("signature_missing_from_instruction")
    if not comp or comp not in instr:
        reasons.append("complexity_missing_from_instruction")
    if not ret or ret not in instr:
        reasons.append("return_contract_missing_from_instruction")
    if not banned or not all(b in instr for b in banned):
        reasons.append("forbidden_constructs_missing_from_instruction")
    if "docstring Bahasa Indonesia" not in instr:
        reasons.append("docstring_requirement_missing_from_instruction")

    ref_code = candidate.get("reference_code")
    if not isinstance(ref_code, str) or not ref_code.strip():
        reasons.append("missing_reference_code")
        return False, reasons

    try:
        tree = ast.parse(ref_code)
    except SyntaxError as exc:
        reasons.append(f"syntax_error:{exc.msg}")
        return False, reasons

    fn_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    fn_name = str(candidate.get("signature_name", ""))
    matching_fns = [n for n in fn_defs if n.name == fn_name]
    if not matching_fns:
        reasons.append("signature_mismatch_in_reference_code")
    else:
        doc = ast.get_docstring(matching_fns[0]) or ""
        if len(doc.split()) < 4:
            reasons.append("missing_or_trivial_docstring")

    ast_hits = _has_forbidden_ast_construct(ref_code, banned)
    if ast_hits:
        reasons.append(f"forbidden_construct_used:{sorted(set(ast_hits))}")

    smoke_check = candidate.get("smoke_check")
    if callable(smoke_check) and not reasons:
        ns: dict[str, Any] = {}
        try:
            exec(compile(tree, "<d9_candidate>", "exec"), ns, ns)
            if not smoke_check(ns):
                reasons.append("smoke_check_returned_false")
        except Exception as exc:
            reasons.append(f"smoke_check_exception:{exc}")

    return len(reasons) == 0, reasons


def _build_language_pool(seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    pool: list[dict[str, Any]] = []
    for s_idx, scenario in enumerate(LANG_SCENARIOS):
        for m_idx, sentences in enumerate(scenario.sentence_modes):
            sample = " ".join(sentences)
            exact_w = len(tokenize_words(sample))
            exact_s = len(split_sentences(sample))
            for t_idx, ctx_tag in enumerate(DOMAIN_CONTEXT_TAGS):
                rot = (s_idx + m_idx + t_idx) % len(scenario.forbidden_roots)
                forb = [
                    scenario.forbidden_roots[(i + rot) % len(scenario.forbidden_roots)]
                    for i in range(len(scenario.forbidden_roots))
                ]
                p1, p2 = scenario.phrases
                f_a, f_b = scenario.ordered_facts
                forb_str = ", ".join(f"`{r}` (beserta imbuhan)" for r in forb)
                instruction = (
                    f"[D9-ID {exact_w}w/{exact_s}s | {ctx_tag}] {scenario.opening_prefix}: "
                    f"{scenario.topic_prompt} "
                    f"Kendala-1: panjang TEPAT {exact_w} kata. "
                    f"Kendala-2: struktur TEPAT {exact_s} kalimat. "
                    f'Kendala-3: wajib memuat frasa persis "{p1}" dan "{p2}". '
                    f"Kendala-4: dilarang memakai akar kata/turunan {forb_str}. "
                    f'Kendala-5: fakta "{f_a}" wajib muncul sebelum "{f_b}".'
                )
                pool.append(
                    {
                        "task_kind": "language",
                        "domain": scenario.domain,
                        "instruction": instruction,
                        "reference_answer": sample,
                        "constraint_count": 5,
                        "constraint_spec": {
                            "episode_id": "",
                            "word_count": {"exact": exact_w},
                            "sentence_count": {"exact": exact_s},
                            "required_phrases": [p1, p2],
                            "forbidden_affix_roots": forb,
                            "required_order": [f_a, f_b],
                        },
                    }
                )
    rng.shuffle(pool)
    return pool


def _build_code_pool(seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed ^ 0x5A5A5A5A)
    pool: list[dict[str, Any]] = []
    for spec in CODE_SPECS:
        for angle in _VARIANT_ANGLES:
            for e_idx in range(len(spec.edge_cases)):
                e_pair = (spec.edge_cases[e_idx], spec.edge_cases[(e_idx + 1) % len(spec.edge_cases)])
                banned_str = ", ".join(spec.forbidden_constructs)
                instruction = (
                    f"[D9-CODE {spec.family} | {angle}] {spec.lead_prompt} "
                    f"Kendala-1 (Signature): `{spec.exact_signature}`. "
                    f"Kendala-2 (Kompleksitas): {spec.complexity_bound}. "
                    f"Kendala-3 (Larangan): dilarang keras memakai `{banned_str}`. "
                    f"Kendala-4 (Kontrak & Kasus Tepi): {spec.return_contract} "
                    f"Selesaikan kasus tepi: {e_pair[0]}; {e_pair[1]}. "
                    f"Kendala-5 (Dokumentasi): {spec.indonesian_docstring_req}"
                )
                pool.append(
                    {
                        "task_kind": "code",
                        "family": spec.family,
                        "signature_name": spec.signature_name,
                        "instruction": instruction,
                        "reference_code": spec.reference_code,
                        "smoke_check": spec.smoke_fn_source_checks,
                        "constraint_count": 5,
                        "code_constraints": {
                            "exact_signature": spec.exact_signature,
                            "complexity_bound": spec.complexity_bound,
                            "forbidden_constructs": list(spec.forbidden_constructs),
                            "return_contract": spec.return_contract,
                            "indonesian_docstring": spec.indonesian_docstring_req,
                        },
                    }
                )
    rng.shuffle(pool)
    return pool


def _validate_prefix(prefix: str, label: str) -> str:
    if not isinstance(prefix, str) or not prefix.strip() or any(ch.isspace() for ch in prefix):
        raise DiscriminatingFactoryError(f"{label} wajib string non-kosong tanpa spasi.")
    return prefix


def generate_discriminating_candidates(
    *,
    lang_count: int = 8,
    code_count: int = 8,
    seed: int = 20261119,
    lang_prefix: str = DEFAULT_LANG_PREFIX,
    code_prefix: str = DEFAULT_CODE_PREFIX,
    frozen_paths: Sequence[Path] | None = None,
    injected_bad_candidates: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Bangun kandidat pembeda bahasa + kode; yang gagal gerbang internal dibuang sebelum ditulis."""
    for label, val in (("lang_count", lang_count), ("code_count", code_count), ("seed", seed)):
        if isinstance(val, bool) or not isinstance(val, int) or val < 0:
            raise DiscriminatingFactoryError(f"{label} wajib integer >= 0.")
    if lang_count == 0 and code_count == 0:
        raise DiscriminatingFactoryError("Minimal satu dari lang_count atau code_count harus > 0.")

    lp = _validate_prefix(lang_prefix, "lang_prefix")
    cp = _validate_prefix(code_prefix, "code_prefix")
    if lp == cp and lang_count > 0 and code_count > 0:
        raise DiscriminatingFactoryError("lang_prefix dan code_prefix harus berbeda agar ID selalu unik.")

    frozen_prefixes: dict[str, dict[str, Any]] = {}
    if frozen_paths:
        frozen_prefixes = load_frozen_prefixes(list(frozen_paths))
    seen_p60: set[str] = set(frozen_prefixes.keys())
    seen_ids: set[str] = set()

    lang_pool = _build_language_pool(seed)
    code_pool = _build_code_pool(seed)
    if injected_bad_candidates:
        bad_lang = [dict(c) for c in injected_bad_candidates if c.get("task_kind") == "language"]
        bad_code = [dict(c) for c in injected_bad_candidates if c.get("task_kind") == "code"]
        lang_pool = bad_lang + lang_pool
        code_pool = bad_code + code_pool

    rejected: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    language_specs: list[dict[str, Any]] = []
    code_specs: list[dict[str, Any]] = []

    width_lang = max(3, len(str(lang_count)))
    width_code = max(3, len(str(code_count)))

    lang_selected = 0
    for cand in lang_pool:
        if lang_selected >= lang_count:
            break
        ok, reasons = verify_language_candidate_internal(cand)
        if not ok:
            rejected.append({"task_kind": "language", "reasons": reasons})
            continue
        instr = cand["instruction"]
        p60 = instr[:60]
        if p60 in seen_p60:
            rejected.append({"task_kind": "language", "reasons": ["prefix60_collision"]})
            continue
        seen_p60.add(p60)
        lang_selected += 1
        ep_id = f"{lp}{lang_selected:0{width_lang}d}"
        if ep_id in seen_ids:
            raise DiscriminatingFactoryError(f"ID duplikat internal: {ep_id}")
        seen_ids.add(ep_id)

        spec = dict(cand["constraint_spec"])
        spec["episode_id"] = ep_id
        spec["constraint_count"] = 5
        episodes.append(
            {
                "id": ep_id,
                "kind": "episode",
                "task_kind": "language",
                "instruction": instr,
            }
        )
        language_specs.append({"id": ep_id, "spec": spec, "reference_answer": cand["reference_answer"]})

    if lang_selected < lang_count:
        raise DiscriminatingFactoryError(
            f"Kandidat language terverifikasi kurang: diminta {lang_count}, dapat {lang_selected}."
        )

    code_selected = 0
    for cand in code_pool:
        if code_selected >= code_count:
            break
        ok, reasons = verify_code_candidate_internal(cand)
        if not ok:
            rejected.append({"task_kind": "code", "reasons": reasons})
            continue
        instr = cand["instruction"]
        p60 = instr[:60]
        if p60 in seen_p60:
            rejected.append({"task_kind": "code", "reasons": ["prefix60_collision"]})
            continue
        seen_p60.add(p60)
        code_selected += 1
        ep_id = f"{cp}{code_selected:0{width_code}d}"
        if ep_id in seen_ids:
            raise DiscriminatingFactoryError(f"ID duplikat internal: {ep_id}")
        seen_ids.add(ep_id)

        episodes.append(
            {
                "id": ep_id,
                "kind": "episode",
                "task_kind": "code",
                "instruction": instr,
            }
        )
        code_specs.append(
            {
                "id": ep_id,
                "signature_name": cand["signature_name"],
                "constraint_count": cand["constraint_count"],
                "code_constraints": cand["code_constraints"],
            }
        )

    if code_selected < code_count:
        raise DiscriminatingFactoryError(
            f"Kandidat code terverifikasi kurang: diminta {code_count}, dapat {code_selected}."
        )

    jsonl_text = "\n".join(json.dumps(ep, ensure_ascii=False) for ep in episodes) + "\n"
    sha256_hex = hashlib.sha256(jsonl_text.encode("utf-8")).hexdigest()

    return {
        "schema": FACTORY_SCHEMA,
        "seed": seed,
        "total_episodes": len(episodes),
        "language_count": lang_selected,
        "code_count": code_selected,
        "rejected_count": len(rejected),
        "rejected": rejected,
        "jsonl_sha256": sha256_hex,
        "jsonl_text": jsonl_text,
        "episodes": episodes,
        "language_specs": language_specs,
        "code_specs": code_specs,
    }


def write_new_candidate_file(
    out_path: Path,
    result: dict[str, Any],
    *,
    meta_path: Path | None = None,
) -> Path:
    """Tulis hasil ke berkas BARU; gagal fail-closed bila target sudah ada."""
    dest = Path(out_path)
    if dest.exists() or dest.is_symlink():
        raise DiscriminatingFactoryError(f"Berkas keluaran sudah ada (keluaran wajib berkas baru): {dest}")
    if meta_path is not None and (meta_path.exists() or meta_path.is_symlink()):
        raise DiscriminatingFactoryError(f"Berkas metadata sudah ada (wajib berkas baru): {meta_path}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(result["jsonl_text"], encoding="utf-8")

    if meta_path is not None:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_doc = {
            "schema": result["schema"],
            "seed": result["seed"],
            "total_episodes": result["total_episodes"],
            "language_count": result["language_count"],
            "code_count": result["code_count"],
            "rejected_count": result["rejected_count"],
            "jsonl_sha256": result["jsonl_sha256"],
            "language_specs": result["language_specs"],
            "code_specs": result["code_specs"],
        }
        meta_path.write_text(json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pabrik kandidat pembeda bahasa (tepat-5 kendala) & kode (>=4 kendala keras)."
    )
    parser.add_argument("--out", type=Path, required=True, help="Path berkas JSONL BARU untuk ditulis")
    parser.add_argument("--meta-out", type=Path, default=None, help="Path berkas JSON BARU opsional untuk spesifikasi kendala")
    parser.add_argument("--lang-count", type=int, default=8, help="Jumlah episode bahasa (default: 8)")
    parser.add_argument("--code-count", type=int, default=8, help="Jumlah episode kode (default: 8)")
    parser.add_argument("--seed", type=int, default=20261119, help="Seed deterministik")
    parser.add_argument("--lang-prefix", default=DEFAULT_LANG_PREFIX, help="Prefix unik ID episode bahasa")
    parser.add_argument("--code-prefix", default=DEFAULT_CODE_PREFIX, help="Prefix unik ID episode kode")
    parser.add_argument("--frozen", type=Path, action="append", default=None, help="Berkas korpus beku read-only untuk anti-kolisi")
    args = parser.parse_args(argv)

    try:
        res = generate_discriminating_candidates(
            lang_count=args.lang_count,
            code_count=args.code_count,
            seed=args.seed,
            lang_prefix=args.lang_prefix,
            code_prefix=args.code_prefix,
            frozen_paths=args.frozen,
        )
        written = write_new_candidate_file(args.out, res, meta_path=args.meta_out)
    except DiscriminatingFactoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summary = {
        "schema": res["schema"],
        "out": str(written),
        "seed": res["seed"],
        "total_episodes": res["total_episodes"],
        "language_count": res["language_count"],
        "code_count": res["code_count"],
        "rejected_count": res["rejected_count"],
        "jsonl_sha256": res["jsonl_sha256"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
