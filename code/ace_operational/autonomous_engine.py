"""Autonomous Engine Daemon for ACE Edition 4 (Continuous OAIE & Language Learning Loop).

Runs continuous cycles of autonomous intelligence evolution:
1. Environment and Model Health Discovery (local GGUF, local deterministic, memory budgets).
2. Agenda processing and task continuation across phases without step-by-step human intervention.
3. Continuous Indonesian Language Learning & Linguistic Curriculum (sentiment, time expressions,
   slang normalization, morphology/affixes, extractive summarization, and dialogue evaluation).
4. MissionBus coordination and worker order delegation with strict lease fencing and independent receipts.
5. Real-time activity projection to 'Cerita ACE' (SSE & SQLite activity ledger).

Runs continuously until interrupted (SIGINT/SIGTERM) or commanded to stop.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any

from ace_indo_nlp.morphology import COLLOQUIAL_SLANG_MAP, analyze_morphology
from ace_operational.autonomy_loop import AutonomyOrchestrator
from ace_operational.coding_loop import CodingAgentLoop
from ace_operational.curriculum_wave2 import LANGUAGE_WAVE2, TECHNICAL_WAVE2
from ace_operational.models_backend import ModelRouter
from ace_operational.self_evolution_engine import SelfEvolutionEngine
from ace_operational.speech_acquisition import SpeechDevelopmentEngine
from ace_operational.store import OperationalStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ACE-AutonomyEngine] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ace_autonomy_engine")


# --- CURRICULUM DEFINITIONS FOR CONTINUOUS INDONESIAN LANGUAGE LEARNING ---
LANGUAGE_CURRICULUM: list[dict[str, Any]] = [
    {
        "skill_name": "analisis_sentimen_dan_emosi_id",
        "domain": "linguistics_sentiment",
        "title": "Analisis Sentimen & Deteksi Emosi Percakapan Indonesia",
        "goal": "Mendeteksi nada santai, positif, negatif, atau netral dari percakapan pengguna bahasa Indonesia",
        "target_file": "projects/learning_lab/bahasa/analisis_sentimen.py",
        "verification_str": "SENTIMEN_VERIFIED_OK",
        "preconditions": ["Teks bahasa Indonesia dalam bentuk string"],
        "procedure_steps": [
            "Tokenisasi kata dari teks masukan",
            "Cocokkan dengan leksikon sentimen bahasa Indonesia",
            "Hitung skor positif vs negatif",
            "Tentukan label polaritas sentimen",
        ],
        "boundary_limitations": ["Leksikon berbasis aturan kata kunci dasar Indonesia"],
        "capability_id": "cap_analisis_sentimen_id",
        "capability_name": "Analisis Sentimen & Nada Emosi Percakapan Indonesia",
        "code": (
            "import re\n\n"
            "LEXICON_POSITIF = frozenset({'bagus', 'keren', 'mantap', 'hebat', 'terima', 'makasih', 'suka', 'senang', 'berhasil', 'sukses', 'top', 'sip', 'oke', 'baik', 'santai'})\n"
            "LEXICON_NEGATIF = frozenset({'jelek', 'buruk', 'lama', 'lambat', 'error', 'gagal', 'rusak', 'kecewa', 'bingung', 'sulit', 'susah', 'pusing', 'ribet', 'parah'})\n\n"
            "def analisis_sentimen(teks: str) -> dict:\n"
            "    kata = re.findall(r'\\w+', teks.lower())\n"
            "    skor_pos = sum(1 for k in kata if k in LEXICON_POSITIF)\n"
            "    skor_neg = sum(1 for k in kata if k in LEXICON_NEGATIF)\n"
            "    if skor_pos > skor_neg:\n"
            "        label = 'positif'\n"
            "    elif skor_neg > skor_pos:\n"
            "        label = 'negatif'\n"
            "    else:\n"
            "        label = 'netral'\n"
            "    return {'label': label, 'skor_positif': skor_pos, 'skor_negatif': skor_neg, 'total_kata': len(kata)}\n\n"
            "if __name__ == '__main__':\n"
            "    assert analisis_sentimen('Terima kasih banyak, hasilnya bagus dan mantap!')['label'] == 'positif'\n"
            "    assert analisis_sentimen('Ini error terus dan bikin pusing, gagal jalan')['label'] == 'negatif'\n"
            "    assert analisis_sentimen('Saya membaca buku di atas meja')['label'] == 'netral'\n"
            "    print('SENTIMEN_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "ekstraksi_entitas_waktu_id",
        "domain": "linguistics_time",
        "title": "Ekstraksi Entitas Waktu Relatif Bahasa Indonesia",
        "goal": "Mengekstrak penanda waktu percakapan sehari-hari bahasa Indonesia (hari ini, besok, lusa, kemarin)",
        "target_file": "projects/learning_lab/bahasa/ekstraksi_waktu.py",
        "verification_str": "WAKTU_VERIFIED_OK",
        "preconditions": ["Teks bahasa Indonesia dengan rujukan waktu"],
        "procedure_steps": [
            "Deteksi penanda waktu relatif dalam kalimat",
            "Hitung offset hari relatif terhadap hari ini",
            "Kembalikan entitas terstruktur",
        ],
        "boundary_limitations": ["Rujukan waktu hari kalender umum"],
        "capability_id": "cap_ekstraksi_entitas_waktu_id",
        "capability_name": "Ekstraksi Entitas & Rujukan Waktu Relatif Indonesia",
        "code": (
            "WAKTU_MAP = {\n"
            "    'kemarin lusa': -2,\n"
            "    'kemarin': -1,\n"
            "    'tadi': -0.5,\n"
            "    'hari ini': 0,\n"
            "    'sekarang': 0,\n"
            "    'besok': 1,\n"
            "    'lusa': 2,\n"
            "    'minggu depan': 7,\n"
            "    'bulan depan': 30,\n"
            "}\n\n"
            "def ekstrak_waktu(teks: str) -> dict:\n"
            "    lower = teks.lower()\n"
            "    ditemukan = []\n"
            "    for k, offset in WAKTU_MAP.items():\n"
            "        if k in lower:\n"
            "            ditemukan.append({'frasa': k, 'offset_hari': offset})\n"
            "    return {'ada_waktu': len(ditemukan) > 0, 'ekspresi': ditemukan}\n\n"
            "if __name__ == '__main__':\n"
            "    r1 = ekstrak_waktu('Besok kita lanjutkan tugas rekap bulanan')\n"
            "    assert r1['ada_waktu'] is True and r1['ekspresi'][0]['offset_hari'] == 1\n"
            "    r2 = ekstrak_waktu('Kemarin pengeluaran belanja sudah tercatat')\n"
            "    assert r2['ekspresi'][0]['offset_hari'] == -1\n"
            "    print('WAKTU_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "kamus_slang_dan_idiom_gaul_id",
        "domain": "linguistics_slang",
        "title": "Penerjemah Slang & Idiom Gaul Bahasa Indonesia",
        "goal": "Menormalkan ungkapan gaul percakapan Indonesia (mager, baper, santuy, gercep, gaskeun)",
        "target_file": "projects/learning_lab/bahasa/slang_normalizer.py",
        "verification_str": "SLANG_VERIFIED_OK",
        "preconditions": ["Teks percakapan ragam santai/informal"],
        "procedure_steps": [
            "Pecah teks menjadi token",
            "Ganti kata slang dengan padanan bahasa Indonesia baku/formal",
            "Rekonstruksi kalimat secara rapi",
        ],
        "boundary_limitations": ["Kosakata slang populer perkotaan"],
        "capability_id": "cap_kamus_slang_id",
        "capability_name": "Pemahaman Slang & Idiom Gaul Percakapan Indonesia",
        "code": (
            "import re\n\n"
            "SLANG_DICT = {\n"
            "    'mager': 'malas gerak',\n"
            "    'baper': 'bawa perasaan',\n"
            "    'kepo': 'penasaran',\n"
            "    'santuy': 'santai',\n"
            "    'woles': 'santai',\n"
            "    'gercep': 'gerak cepat',\n"
            "    'gaskeun': 'ayo mulai',\n"
            "    'mantul': 'mantap betul',\n"
            "    'gokil': 'luar biasa',\n"
            "    'ngab': 'saudara',\n"
            "}\n\n"
            "def terjemahkan_slang(teks: str) -> str:\n"
            "    tokens = re.findall(r'\\w+|[^\\w\\s]', teks)\n"
            "    hasil = [SLANG_DICT.get(t.lower(), t) for t in tokens]\n"
            "    out = ''\n"
            "    for i, t in enumerate(hasil):\n"
            "        if i > 0 and re.match(r'\\w+', t) and re.match(r'\\w+', hasil[i-1]):\n"
            "            out += ' ' + t\n"
            "        elif i > 0 and t not in (',', '.', '?', '!'):\n"
            "            out += ' ' + t\n"
            "        else:\n"
            "            out += t\n"
            "    return out\n\n"
            "if __name__ == '__main__':\n"
            "    t1 = terjemahkan_slang('Jangan mager, ayo gercep gaskeun')\n"
            "    assert 'malas gerak' in t1 and 'gerak cepat' in t1 and 'ayo mulai' in t1\n"
            "    assert 'santai' in terjemahkan_slang('Santuy saja ngab')\n"
            "    print('SLANG_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "analisis_morfologi_imbuhan_id",
        "domain": "linguistics_morphology",
        "title": "Analisis Morfologi & Kata Dasar Bahasa Indonesia",
        "goal": "Mengekstrak kata dasar dari kata berimbuhan me-, ber-, di-, ter-, -kan, -an",
        "target_file": "projects/learning_lab/bahasa/morfologi_imbuhan.py",
        "verification_str": "MORFOLOGI_VERIFIED_OK",
        "preconditions": ["Kata turunan berimbuhan bahasa Indonesia"],
        "procedure_steps": [
            "Identifikasi prefiks dan sufiks",
            "Ekstrak kata dasar secara bertahap",
            "Kembalikan informasi afiksasi",
        ],
        "boundary_limitations": ["Heuristik pola afiks standar Indonesia"],
        "capability_id": "cap_analisis_morfologi_id",
        "capability_name": "Analisis Morfologi & Afiksasi Bahasa Indonesia",
        "code": (
            "PREFIKS = ('meng', 'meny', 'men', 'mem', 'me', 'ber', 'ter', 'di', 'pe', 'per', 'ke')\n"
            "SUFIKS = ('kan', 'an', 'i')\n\n"
            "def ekstrak_kata_dasar(kata: str) -> dict:\n"
            "    w = kata.lower().strip()\n"
            "    pref_found = ''\n"
            "    suf_found = ''\n"
            "    for p in PREFIKS:\n"
            "        if w.startswith(p) and len(w) > len(p) + 2:\n"
            "            pref_found = p\n"
            "            w = w[len(p):]\n"
            "            break\n"
            "    for s in SUFIKS:\n"
            "        # Over-stemming guard: the remaining stem must keep\n"
            "        # at least 4 characters, so a root that merely ends\n"
            "        # in a suffix-like letter ('lari' -> 'lar') is not\n"
            "        # truncated into a non-root.\n"
            "        if w.endswith(s) and len(w) - len(s) >= 4:\n"
            "            suf_found = s\n"
            "            w = w[:-len(s)]\n"
            "            break\n"
            "    return {'kata_dasar': w, 'prefiks': pref_found, 'sufiks': suf_found}\n\n"
            "if __name__ == '__main__':\n"
            "    r1 = ekstrak_kata_dasar('menuliskan')\n"
            "    assert r1['prefiks'] == 'men' and r1['sufiks'] == 'kan'\n"
            "    r2 = ekstrak_kata_dasar('berlari')\n"
            "    assert r2['prefiks'] == 'ber' and r2['kata_dasar'] == 'lari'\n"
            "    print('MORFOLOGI_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "ringkasan_teks_ekstraktif_id",
        "domain": "linguistics_summarization",
        "title": "Peringkas Teks Ekstraktif Bahasa Indonesia",
        "goal": "Mengekstrak kalimat paling informatif dari paragraf bahasa Indonesia tanpa kata henti",
        "target_file": "projects/learning_lab/bahasa/ringkas_teks.py",
        "verification_str": "RINGKASAN_VERIFIED_OK",
        "preconditions": ["Teks paragraf bahasa Indonesia"],
        "procedure_steps": [
            "Pisahkan kalimat-kalimat dalam paragraf",
            "Hitung bobot kata bermakna (abaikan stopwords)",
            "Pilih kalimat dengan skor tertinggi",
        ],
        "boundary_limitations": ["Peringkasan ekstraktif kalimat tunggal/ganda"],
        "capability_id": "cap_ringkasan_teks_id",
        "capability_name": "Peringkasan Teks Ekstraktif Bahasa Indonesia",
        "code": (
            "import re\n\n"
            "STOPWORDS = frozenset({'dan', 'di', 'ke', 'dari', 'yang', 'untuk', 'ini', 'itu', 'adalah', 'dengan', 'pada', 'oleh', 'dalam'})\n\n"
            "def ringkas_teks(paragraf: str, max_kalimat: int = 1) -> str:\n"
            "    kalimat = [k.strip() for k in re.split(r'[.!?]+', paragraf) if k.strip()]\n"
            "    if not kalimat:\n"
            "        return ''\n"
            "    skor_kalimat = []\n"
            "    for k in kalimat:\n"
            "        kata = [w for w in re.findall(r'\\w+', k.lower()) if w not in STOPWORDS]\n"
            "        skor_kalimat.append((len(kata), k))\n"
            "    skor_kalimat.sort(key=lambda x: x[0], reverse=True)\n"
            "    terpilih = [item[1] for item in skor_kalimat[:max_kalimat]]\n"
            "    return '. '.join(terpilih) + '.'\n\n"
            "if __name__ == '__main__':\n"
            "    teks = 'Bahasa Indonesia adalah bahasa persatuan. Penggunaan kalimat efektif sangat penting dalam dialog interaktif AI.'\n"
            "    r = ringkas_teks(teks, 1)\n"
            "    assert len(r) > 10 and r.endswith('.')\n"
            "    print('RINGKASAN_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "evaluasi_kualitas_dialog_id",
        "domain": "linguistics_dialogue_quality",
        "title": "Evaluator Kualitas & Kesopanan Dialog Bahasa Indonesia",
        "goal": "Menilai panjang ideal, kesantunan, dan kelayakan respons dialog Bahasa Indonesia",
        "target_file": "projects/learning_lab/bahasa/evaluasi_dialog.py",
        "verification_str": "EVALUASI_DIALOG_VERIFIED_OK",
        "preconditions": ["Teks respons percakapan bahasa Indonesia"],
        "procedure_steps": [
            "Hitung jumlah kata dan verifikasi panjang kalimat ideal",
            "Periksa kata santun dan komunikatif",
            "Kembalikan skor kelayakan dialog",
        ],
        "boundary_limitations": ["Evaluasi dialog komunikatif"],
        "capability_id": "cap_evaluasi_dialog_id",
        "capability_name": "Evaluasi Kualitas & Kesantunan Dialog Bahasa Indonesia",
        "code": (
            "import re\n\n"
            "KATA_SOPAN = frozenset({'tolong', 'terima kasih', 'makasih', 'mohon', 'maaf', 'silakan', 'baik', 'siap', 'senang'})\n\n"
            "def evaluasi_dialog(teks: str) -> dict:\n"
            "    kata = re.findall(r'\\w+', teks.lower())\n"
            "    total_kata = len(kata)\n"
            "    sopan_count = sum(1 for k in kata if k in KATA_SOPAN)\n"
            "    skor_kesopanan = min(1.0, round(sopan_count / 2, 2))\n"
            "    panjang_ideal = 5 <= total_kata <= 90\n"
            "    return {\n"
            "        'total_kata': total_kata,\n"
            "        'panjang_ideal': panjang_ideal,\n"
            "        'skor_kesopanan': skor_kesopanan,\n"
            "        'layak': panjang_ideal,\n"
            "    }\n\n"
            "if __name__ == '__main__':\n"
            "    ev = evaluasi_dialog('Terima kasih banyak, saya siap membantu menyelesaikan tugas Anda.')\n"
            "    assert ev['layak'] is True and ev['skor_kesopanan'] >= 0.5\n"
            "    print('EVALUASI_DIALOG_VERIFIED_OK')\n"
        ),
    },
    *LANGUAGE_WAVE2,
]


# --- CURRICULUM DEFINITIONS FOR CONTINUOUS TECHNICAL ENGINEERING LEARNING ---
TECHNICAL_CURRICULUM: list[dict[str, Any]] = [
    {
        "skill_name": "algoritma_dijkstra_rute_terpendek",
        "domain": "engineering_algorithms",
        "title": "Algoritma Dijkstra Rute Terpendek Graf Berbobot",
        "goal": "Menghitung jarak dan jalur terpendek pada graf berbobot dengan penanganan simpul tak terjangkau",
        "target_file": "projects/learning_lab/teknis/dijkstra_router.py",
        "verification_str": "DIJKSTRA_VERIFIED_OK",
        "preconditions": ["Representasi adjacency list dengan bobot non-negatif"],
        "procedure_steps": [
            "Validasi bobot non-negatif pada setiap sisi graf",
            "Gunakan priority queue (heapq) untuk memilih simpul terdekat",
            "Rekonstruksi lintasan optimal beserta jarak totalnya",
        ],
        "boundary_limitations": ["Bobot sisi harus bernilai >= 0"],
        "capability_id": "cap_algoritma_graf_dijkstra",
        "capability_name": "Algoritma Pencarian Rute Terpendek Graf (Dijkstra)",
        "code": (
            "import heapq\n\n"
            "def rute_terpendek(graf: dict[str, list[tuple[str, float]]], awal: str, tujuan: str) -> dict:\n"
            "    if awal not in graf or tujuan not in graf:\n"
            "        return {'terjangkau': False, 'jarak': None, 'jalur': []}\n"
            "    dist = {awal: 0.0}\n"
            "    prev: dict[str, str | None] = {awal: None}\n"
            "    pq: list[tuple[float, str]] = [(0.0, awal)]\n"
            "    while pq:\n"
            "        d, u = heapq.heappop(pq)\n"
            "        if d > dist.get(u, float('inf')):\n"
            "            continue\n"
            "        if u == tujuan:\n"
            "            break\n"
            "        for v, w in graf.get(u, []):\n"
            "            if w < 0:\n"
            "                raise ValueError(f'Bobot negatif tidak diizinkan: {u}->{v}={w}')\n"
            "            nd = d + w\n"
            "            if nd < dist.get(v, float('inf')):\n"
            "                dist[v] = nd\n"
            "                prev[v] = u\n"
            "                heapq.heappush(pq, (nd, v))\n"
            "    if tujuan not in dist:\n"
            "        return {'terjangkau': False, 'jarak': None, 'jalur': []}\n"
            "    jalur = []\n"
            "    cur: str | None = tujuan\n"
            "    while cur is not None:\n"
            "        jalur.append(cur)\n"
            "        cur = prev.get(cur)\n"
            "    jalur.reverse()\n"
            "    return {'terjangkau': True, 'jarak': dist[tujuan], 'jalur': jalur}\n\n"
            "if __name__ == '__main__':\n"
            "    g = {'A': [('B', 2), ('C', 5)], 'B': [('C', 1), ('D', 4)], 'C': [('D', 1)], 'D': [], 'Z': []}\n"
            "    r1 = rute_terpendek(g, 'A', 'D')\n"
            "    assert r1['terjangkau'] is True and r1['jarak'] == 4.0 and r1['jalur'] == ['A', 'B', 'C', 'D']\n"
            "    r2 = rute_terpendek(g, 'A', 'Z')\n"
            "    assert r2['terjangkau'] is False and r2['jalur'] == []\n"
            "    print('DIJKSTRA_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "pemeriksa_kompleksitas_ast_python",
        "domain": "engineering_ast",
        "title": "Inspeksi Kualitas & Kompleksitas Percabangan AST Python",
        "goal": "Menganalisis AST modul Python untuk menghitung jumlah cabang dan mendeteksi except sunyi",
        "target_file": "projects/learning_lab/teknis/ast_complexity.py",
        "verification_str": "AST_COMPLEXITY_VERIFIED_OK",
        "preconditions": ["Kode sumber Python valid dalam bentuk string"],
        "procedure_steps": [
            "Parse source code menjadi pohon AST",
            "Hitung cabang logika per fungsi",
            "Deteksi handler except Exception: pass",
        ],
        "boundary_limitations": ["Analisis statis AST tanpa eksekusi kode target"],
        "capability_id": "cap_ast_complexity_auditor",
        "capability_name": "Pemeriksa Kompleksitas Percabangan & Pola Except AST",
        "code": (
            "import ast\n\n"
            "BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With)\n\n"
            "def analisis_modul(sumber: str) -> dict:\n"
            "    tree = ast.parse(sumber)\n"
            "    fungsi = []\n"
            "    silent_except = 0\n"
            "    for node in ast.walk(tree):\n"
            "        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
            "            cabang = 1 + sum(1 for n in ast.walk(node) if isinstance(n, BRANCH_NODES))\n"
            "            fungsi.append({'nama': node.name, 'kompleksitas': cabang})\n"
            "        elif isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):\n"
            "            silent_except += 1\n"
            "    return {'jumlah_fungsi': len(fungsi), 'fungsi': fungsi, 'silent_except': silent_except}\n\n"
            "if __name__ == '__main__':\n"
            "    contoh = 'def f(x):\\n    if x > 0:\\n        return x\\n    try:\\n        return 1//x\\n    except Exception:\\n        pass\\n'\n"
            "    hasil = analisis_modul(contoh)\n"
            "    assert hasil['jumlah_fungsi'] == 1 and hasil['fungsi'][0]['kompleksitas'] >= 3\n"
            "    assert hasil['silent_except'] == 1\n"
            "    print('AST_COMPLEXITY_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "etl_csv_json_validasi_sha256",
        "domain": "engineering_data_etl",
        "title": "Pipeline ETL CSV ke JSON Tervalidasi & Checksum SHA-256",
        "goal": "Mengolah baris CSV dengan karantina data rusak serta menghasilkan JSON kanonis bersegel SHA-256",
        "target_file": "projects/learning_lab/teknis/etl_csv_sha256.py",
        "verification_str": "ETL_SHA256_VERIFIED_OK",
        "preconditions": ["Teks CSV memiliki header kategori dan nilai"],
        "procedure_steps": [
            "Baca baris CSV dan pisahkan baris tidak valid ke daftar karantina",
            "Agregasi total nilai per kategori secara deterministik",
            "Hitung digest SHA-256 atas keluaran JSON kanonis",
        ],
        "boundary_limitations": ["Memproses data CSV bertipe numerik pada kolom nilai"],
        "capability_id": "cap_etl_csv_sha256",
        "capability_name": "Pipeline ETL CSV ke JSON Kanonis & Verifikasi SHA-256",
        "code": (
            "import csv\n"
            "import hashlib\n"
            "import io\n"
            "import json\n\n"
            "def proses_etl_csv(csv_text: str) -> dict:\n"
            "    reader = csv.DictReader(io.StringIO(csv_text.strip()))\n"
            "    totals: dict[str, int] = {}\n"
            "    karantina: list[dict] = []\n"
            "    valid_rows = 0\n"
            "    for idx, row in enumerate(reader, start=1):\n"
            "        kat = (row.get('kategori') or '').strip().lower()\n"
            "        raw_val = (row.get('nilai') or '').strip()\n"
            "        try:\n"
            "            val = int(raw_val)\n"
            "            if not kat:\n"
            "                raise ValueError('kategori kosong')\n"
            "            totals[kat] = totals.get(kat, 0) + val\n"
            "            valid_rows += 1\n"
            "        except ValueError as err:\n"
            "            karantina.append({'baris': idx, 'error': str(err)})\n"
            "    canonical = json.dumps(totals, sort_keys=True, separators=(',', ':'))\n"
            "    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()\n"
            "    return {'valid_rows': valid_rows, 'karantina': karantina, 'totals': totals, 'sha256': digest}\n\n"
            "if __name__ == '__main__':\n"
            "    sample = 'kategori,nilai\\npangan,15000\\ntransport,abc\\npangan,5000\\n,100\\n'\n"
            "    res = proses_etl_csv(sample)\n"
            "    assert res['valid_rows'] == 2 and res['totals']['pangan'] == 20000\n"
            "    assert len(res['karantina']) == 2 and len(res['sha256']) == 64\n"
            "    print('ETL_SHA256_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "kalkulator_finansial_cagr_roi",
        "domain": "engineering_finance",
        "title": "Kalkulator Metrik Finansial (ROI, CAGR, Break-Even) Aman Pembagian Nol",
        "goal": "Menghitung ROI, CAGR, dan titik impas dengan penjagaan input nol atau negatif",
        "target_file": "projects/learning_lab/teknis/finance_metrics.py",
        "verification_str": "FINANCE_METRICS_VERIFIED_OK",
        "preconditions": ["Parameter numerik modal, nilai akhir, dan periode"],
        "procedure_steps": [
            "Validasi pembagi dan periode positif sebelum menghitung rasio",
            "Hitung persentase ROI dan tingkat pertumbuhan majemuk CAGR",
            "Hitung unit break-even dengan aman ketika margin <= 0",
        ],
        "boundary_limitations": ["CAGR memerlukan nilai awal > 0 dan tahun > 0"],
        "capability_id": "cap_kalkulasi_finansial_aman",
        "capability_name": "Kalkulasi Metrik Finansial (ROI, CAGR, BEP) Tahan Error",
        "code": (
            "def hitung_roi_persen(modal: float, hasil_bersih: float) -> float | None:\n"
            "    if modal <= 0:\n"
            "        return None\n"
            "    return round(((hasil_bersih - modal) / modal) * 100.0, 2)\n\n"
            "def hitung_cagr_persen(awal: float, akhir: float, tahun: float) -> float | None:\n"
            "    if awal <= 0 or akhir < 0 or tahun <= 0:\n"
            "        return None\n"
            "    return round(((akhir / awal) ** (1.0 / tahun) - 1.0) * 100.0, 2)\n\n"
            "def hitung_break_even(biaya_tetap: float, harga_jual: float, biaya_variabel: float) -> float | None:\n"
            "    margin = harga_jual - biaya_variabel\n"
            "    if margin <= 0:\n"
            "        return None\n"
            "    return round(biaya_tetap / margin, 2)\n\n"
            "if __name__ == '__main__':\n"
            "    assert hitung_roi_persen(1000.0, 1250.0) == 25.0\n"
            "    assert hitung_roi_persen(0.0, 500.0) is None\n"
            "    assert hitung_cagr_persen(100.0, 121.0, 2.0) == 10.0\n"
            "    assert hitung_break_even(100000.0, 15000.0, 15000.0) is None\n"
            "    assert hitung_break_even(100000.0, 25000.0, 15000.0) == 10.0\n"
            "    print('FINANCE_METRICS_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "parser_log_http_deteksi_anomali",
        "domain": "engineering_observability",
        "title": "Parser Log HTTP & Detektor Anomali Latensi P95",
        "goal": "Menganalisis baris log permintaan HTTP untuk menghitung rasio error dan lonjakan latensi p95",
        "target_file": "projects/learning_lab/teknis/log_anomaly_parser.py",
        "verification_str": "LOG_ANOMALY_VERIFIED_OK",
        "preconditions": ["Log baris berbentuk 'METHOD /endpoint STATUS LATENCYms'"],
        "procedure_steps": [
            "Ekstrak method, path, status HTTP, dan latensi per baris via regex",
            "Hitung persentil ke-95 (p95) latensi dan persentase status >= 500",
            "Tandai anomali jika latensi melebihi ambang SLA",
        ],
        "boundary_limitations": ["Format baris log standar layanan HTTP internal"],
        "capability_id": "cap_observability_log_parser",
        "capability_name": "Parser Log HTTP & Deteksi Anomali Latensi Layanan",
        "code": (
            "import re\n\n"
            "LOG_RE = re.compile(r'^(GET|POST|PUT|DELETE)\\s+(\\S+)\\s+(\\d{3})\\s+(\\d+(?:\\.\\d+)?)ms$')\n\n"
            "def audit_log_http(baris_log: list[str], sla_ms: float = 250.0) -> dict:\n"
            "    latensi: list[float] = []\n"
            "    error_5xx = 0\n"
            "    anomali: list[str] = []\n"
            "    for raw in baris_log:\n"
            "        m = LOG_RE.match(raw.strip())\n"
            "        if not m:\n"
            "            continue\n"
            "        _, path, code_str, ms_str = m.groups()\n"
            "        code = int(code_str)\n"
            "        ms = float(ms_str)\n"
            "        latensi.append(ms)\n"
            "        if code >= 500:\n"
            "            error_5xx += 1\n"
            "        if ms > sla_ms:\n"
            "            anomali.append(f'{path}:{ms}ms')\n"
            "    if not latensi:\n"
            "        return {'total': 0, 'p95_ms': 0.0, 'error_5xx': 0, 'anomali': []}\n"
            "    lat_sorted = sorted(latensi)\n"
            "    idx = min(len(lat_sorted) - 1, int(0.95 * (len(lat_sorted) - 1)))\n"
            "    return {'total': len(latensi), 'p95_ms': lat_sorted[idx], 'error_5xx': error_5xx, 'anomali': anomali}\n\n"
            "if __name__ == '__main__':\n"
            "    logs = ['GET /api/status 200 18.5ms', 'POST /api/chat 502 420.0ms', 'GET /api/events 200 32.0ms']\n"
            "    res = audit_log_http(logs, sla_ms=250.0)\n"
            "    assert res['total'] == 3 and res['error_5xx'] == 1 and len(res['anomali']) == 1\n"
            "    assert audit_log_http([])['total'] == 0\n"
            "    print('LOG_ANOMALY_VERIFIED_OK')\n"
        ),
    },
    {
        "skill_name": "latihan_perbaikan_concurrency_dan_edgecase",
        "domain": "engineering_reliability",
        "title": "Pembatas Laju Sliding-Window Thread-Safe",
        "goal": "Mengimplementasikan pembatas permintaan berbasis jendela waktu geser yang aman terhadap race condition",
        "target_file": "projects/learning_lab/teknis/rate_limiter_sliding.py",
        "verification_str": "RATE_LIMITER_VERIFIED_OK",
        "preconditions": ["Konfigurasi batas permintaan dan lebar jendela waktu > 0"],
        "procedure_steps": [
            "Lindungi antrean stempel waktu dengan threading.Lock",
            "Buang timestamp yang sudah melewati jendela geser",
            "Uji permintaan serentak dari beberapa thread",
        ],
        "boundary_limitations": ["In-memory per proses"],
        "capability_id": "cap_sliding_window_rate_limiter",
        "capability_name": "Pembatas Laju Sliding-Window Thread-Safe",
        "code": (
            "from collections import deque\n"
            "import threading\n"
            "import time\n\n"
            "class SlidingWindowLimiter:\n"
            "    def __init__(self, max_requests: int, window_seconds: float):\n"
            "        if max_requests < 1 or window_seconds <= 0:\n"
            "            raise ValueError('Konfigurasi rate limiter harus positif')\n"
            "        self.max_requests = max_requests\n"
            "        self.window_seconds = window_seconds\n"
            "        self._lock = threading.Lock()\n"
            "        self._hits: dict[str, deque[float]] = {}\n\n"
            "    def allow(self, key: str, now: float | None = None) -> bool:\n"
            "        ts = time.monotonic() if now is None else now\n"
            "        with self._lock:\n"
            "            q = self._hits.setdefault(key, deque())\n"
            "            cutoff = ts - self.window_seconds\n"
            "            while q and q[0] <= cutoff:\n"
            "                q.popleft()\n"
            "            if len(q) >= self.max_requests:\n"
            "                return False\n"
            "            q.append(ts)\n"
            "            return True\n\n"
            "if __name__ == '__main__':\n"
            "    lim = SlidingWindowLimiter(max_requests=3, window_seconds=10.0)\n"
            "    results = []\n"
            "    lock = threading.Lock()\n"
            "    def worker():\n"
            "        ok = lim.allow('user1', now=100.0)\n"
            "        with lock:\n"
            "            results.append(ok)\n"
            "    threads = [threading.Thread(target=worker) for _ in range(5)]\n"
            "    for t in threads: t.start()\n"
            "    for t in threads: t.join()\n"
            "    assert results.count(True) == 3 and results.count(False) == 2\n"
            "    assert lim.allow('user1', now=111.0) is True\n"
            "    print('RATE_LIMITER_VERIFIED_OK')\n"
        ),
    },
    *TECHNICAL_WAVE2,
]


TECH_PRACTICE_THEMES: list[str] = [
    "algoritma graf BFS atau deteksi siklus pada struktur dependensi tugas",
    "pencarian biner (binary search) dan penggabungan interval jadwal bertumpuk",
    "parser dan validator konfigurasi JSON/INI dengan penanganan field kosong atau rusak",
    "simulasi retry exponential backoff dan circuit breaker terhadap layanan gagal sementara",
    "deduplikasi baris CSV dan agregasi metrik ringkas yang tahan nilai kosong atau korup",
    "struktur LRU Cache berkapasitas tetap beserta pengujian eviction dan hit/miss",
    "detektor celah keamanan dasar via modul Python AST (misalnya eval, exec, bare except)",
    "penghitung pajak progresif, diskon bertingkat, dan pembulatan transaksi keuangan aman",
    "penilaian kesamaan teks dengan tokenisasi dan cosine similarity sederhana",
    "perbaikan bug fungsi dengan kasus batas pembagian nol, list kosong, dan input negatif",
]


def _resolve_workspace_path(store: OperationalStore | None, workspace: Path | None) -> Path:
    if workspace is not None:
        return Path(workspace).expanduser().resolve()
    if store is not None:
        return Path(store.workspace).resolve()
    env_ws = os.environ.get("ACE_WORKSPACE", "").strip()
    if env_ws:
        return Path(env_ws).expanduser().resolve()
    return (Path.home() / ".local" / "share" / "ace" / "workspace").resolve()


class ContinuousAutonomousEngine:
    """Manages indefinite mixed (technical + language) autonomous cycles for ACE."""

    def __init__(
        self,
        store: OperationalStore | None = None,
        workspace: Path | None = None,
        tick_interval_seconds: float = 1.5,
    ):
        self.workspace = _resolve_workspace_path(store, workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = store or OperationalStore(workspace=self.workspace)
        try:
            from .memory_snapshot import import_snapshot_if_needed
            seed_res = import_snapshot_if_needed(self.store)
            if seed_res.get("applied"):
                logger.info(
                    f"[SeedSnapshot] Restored {seed_res.get('words_added', 0)} words & "
                    f"{seed_res.get('memories_added', 0)} memories from Git snapshot"
                )
        except Exception as exc:
            logger.debug(f"Seed snapshot check skipped: {exc}")
        self.orchestrator = AutonomyOrchestrator(self.store)
        self.models = ModelRouter(self.store)
        self.tick_interval_seconds = float(tick_interval_seconds)
        self.running = False
        self.cycle_count = self._load_int_meta("autonomous_cycle_count", 0)
        self._lang_cursor = self._load_int_meta("autonomous_lang_cursor", 0)
        self._tech_cursor = self._load_int_meta("autonomous_tech_cursor", 0)
        self._last_cycle_duration_seconds: float | None = None
        self._slowest_step: dict[str, str | float | None] = {"name": None, "seconds": None}
        self._bridge_transport_failures = 0
        self.status_file = self.workspace / "autonomous_engine.status.json"
        self.corpus_file = self.workspace / "projects" / "bahasa" / "dialog_corpus.jsonl"
        self.corpus_file.parent.mkdir(parents=True, exist_ok=True)
        self.tech_corpus_file = self.workspace / "projects" / "teknis" / "technical_corpus.jsonl"
        self.tech_corpus_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_int_meta(self, key: str, default: int = 0) -> int:
        raw = self.store.get_meta(key, str(default))
        try:
            return max(0, int(raw or default))
        except ValueError:
            return default

    def _persist_cursors(self) -> None:
        self.store.set_meta("autonomous_cycle_count", str(self.cycle_count))
        self.store.set_meta("autonomous_lang_cursor", str(self._lang_cursor))
        self.store.set_meta("autonomous_tech_cursor", str(self._tech_cursor))

    def update_status_file(self, current_action: str, details: dict[str, Any] | None = None) -> None:
        payload = {
            "schema": "ace.autonomous_engine.status.v1",
            "running": self.running,
            "cycle_count": self.cycle_count,
            "lang_cursor": self._lang_cursor,
            "tech_cursor": self._tech_cursor,
            "current_action": current_action,
            "pid": os.getpid(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "details": details or {},
            "last_cycle_duration_seconds": self._last_cycle_duration_seconds,
            "slowest_step": self._slowest_step,
            "bridge_transport_failures": self._bridge_transport_failures,
        }
        try:
            tmp = self.status_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.status_file)
        except OSError as e:
            logger.warning(f"Could not write status file: {e}")

    def verify_and_promote_local_gguf(self) -> bool:
        """Verify local GGUF model readiness and promote cap_local_gguf on Frontier."""
        frontier_items = {c["capability_id"]: c for c in self.store.list_frontier()}
        gguf_cap = frontier_items.get("cap_local_gguf")
        if gguf_cap and gguf_cap.get("status") == "KNOWN_AND_TESTED":
            return True

        disc = self.models.discover_local_gguf()
        if not (disc.get("server_healthy") or disc.get("valid_models")):
            return False

        logger.info("Executing verification test on local GGUF model backend...")
        try:
            gen_res = self.models.generate_text([
                {"role": "user", "content": "Jawab singkat dalam satu kata: Siapakah kamu?"}
            ], max_tokens=32)
            backend_used = gen_res.get("backend_used", "")
            ans = gen_res.get("text", "")
            if ans and "local-gguf" in backend_used:
                self.store.set_frontier_capability(
                    capability_id="cap_local_gguf",
                    name_id="Inferensi Model GGUF Lokal (llama.cpp / llama-server)",
                    category="model",
                    status="KNOWN_AND_TESTED",
                    evidence_ref=f"verified:{backend_used}:{ans[:30]}",
                )
                self.store.emit_event(
                    kind="test_executed",
                    status="COMPLETED",
                    summary_code="Verifikasi Model GGUF Lokal",
                    verification_passed=True,
                    technical_detail={
                        "title_id": "Verifikasi Inferensi GGUF Lokal",
                        "backend_used": backend_used,
                        "sample_response": ans[:60],
                    },
                )
                logger.info(f"Promoted cap_local_gguf to KNOWN_AND_TESTED via {backend_used}")
                return True
        except Exception as e:
            logger.warning(f"GGUF verification probe failed: {e}")
        return False

    def check_and_advance_agenda(self) -> int:
        """Execute queued agenda items if present."""
        agenda = [a for a in self.orchestrator.get_prioritized_agenda() if a.get("status") in ("QUEUED", "PAUSED")]
        if not agenda:
            return 0

        logger.info(f"Advancing {len(agenda)} queued agenda items...")
        res = self.orchestrator.run_autonomous_continuation_cycle(max_steps=2)
        executed_count = len(res.get("executed", []))
        if executed_count > 0:
            logger.info(f"Successfully advanced {executed_count} agenda tasks")
        return executed_count

    def _ensure_developmental_speech_skill(self) -> dict[str, Any] | None:
        existing_skills = {s["name"]: s for s in self.store.list_skills()}
        if "keterampilan_berbicara_bertahap_id" in existing_skills:
            return None
        logger.info("[Language Learning] Menjalankan kurikulum perkembangan berbicara 4 tahap...")
        speech_engine = SpeechDevelopmentEngine(self.store)
        grad = speech_engine.train_and_graduate(
            conversation_id="autonomous_speech_loop",
            user_request="Kurikulum otomatis skill berbicara Bahasa Indonesia 4 tahap",
        )
        if grad.get("passed"):
            receipt_id = grad["stages"][-1]["receipt_id"] if grad.get("stages") else ""
            logger.info("Learned and verified developmental speech skill with receipt %s", receipt_id)
            return {"skill": "keterampilan_berbicara_bertahap_id", "receipt": receipt_id}
        return None

    def _run_verified_curriculum_item(
        self,
        item: dict[str, Any],
        *,
        learning_kind: str,
        category: str,
        verified_by: str,
        task_prefix: str,
    ) -> dict[str, Any]:
        skill_name = item["skill_name"]
        logger.info(f"[Curriculum:{learning_kind}] Advancing {skill_name} ({item['title']})...")
        task = self.store.create_task(
            title_id=item["title"],
            user_request=f"{task_prefix}: {item['title']}",
            normalized_goal=item["goal"],
        )
        self.store.update_task(task["task_id"], status="ACTIVE")
        self.store.emit_event(
            kind="task_started",
            status="ACTIVE",
            summary_code=f"{task_prefix}: {item['title']}",
            technical_detail={"title_id": item["title"], "goal": item["goal"]},
        )

        target_p = self.workspace / item["target_file"]
        target_p.parent.mkdir(parents=True, exist_ok=True)
        target_p.write_text(item["code"], encoding="utf-8")

        comp = subprocess.run([sys.executable, "-m", "py_compile", str(target_p)], capture_output=True, text=True, timeout=10)
        proc = (
            subprocess.run([sys.executable, str(target_p)], capture_output=True, text=True, timeout=10)
            if comp.returncode == 0
            else comp
        )
        passed = comp.returncode == 0 and proc.returncode == 0 and item["verification_str"] in proc.stdout
        receipt = self.store.record_receipt(
            task_id=task["task_id"],
            action_kind=f"execute_{learning_kind}_verification",
            input_data=item["code"],
            output_data=proc.stdout,
            command_or_operation=f"{sys.executable} {target_p}",
            exit_code=proc.returncode,
            stdout_text=proc.stdout,
            stderr_text=proc.stderr,
            artifacts_created=[str(target_p)],
            verified_by=verified_by,
            passed=passed,
        )
        if passed:
            self.store.save_skill(
                name=skill_name,
                domain=item["domain"],
                preconditions=item["preconditions"],
                procedure_steps=item["procedure_steps"],
                verification_template={"module": str(target_p), "receipt_id": receipt["receipt_id"]},
                source_task_ids=[task["task_id"]],
                boundary_limitations=item["boundary_limitations"],
            )
            self.store.set_frontier_capability(
                capability_id=item["capability_id"],
                name_id=item["capability_name"],
                category=category,
                status="KNOWN_AND_TESTED",
                evidence_ref=receipt["receipt_id"],
            )
            self.store.update_task(
                task["task_id"],
                status="COMPLETED",
                verification_summary={"passed": True, "receipt_id": receipt["receipt_id"]},
                artifacts=[str(target_p)],
            )
            self.store.emit_event(
                kind="skill_learned",
                status="COMPLETED",
                summary_code=f"Keterampilan Terverifikasi: {item['title']}",
                verification_passed=True,
                artifact_refs=[str(target_p)],
                technical_detail={
                    "title_id": item["title"],
                    "skill_name": skill_name,
                    "learning_kind": learning_kind,
                    "receipt_id": receipt["receipt_id"],
                },
            )
            writeback_id = self._writeback_skill_verified(
                item=item, receipt=receipt, learning_kind=learning_kind)
            # EVO 0018 M2 — resolve-on-pass: lulusnya verifikasi skill
            # menutup gap verifikasi yang cocok (sebelumnya gap tetap
            # OPEN selamanya walau skill-nya sudah ACTIVE terverifikasi
            # — kasus gap_72e9344d4f). Tugas yang membuktikan lulus
            # menjadi linked_learning_task_id gap itu.
            try:
                wanted_type = f"{learning_kind.upper()}_VERIFICATION_FAILED"
                for gap in self.store.list_gaps(status="OPEN"):
                    if (gap.get("error_type") == wanted_type
                            and gap.get("missing_skill_or_tool") == skill_name):
                        self.store.update_gap(
                            gap["gap_id"], status="RESOLVED",
                            linked_learning_task_id=task["task_id"])
            except Exception:
                logger.warning(
                    "resolve-on-pass gagal untuk %s", skill_name, exc_info=True)
            logger.info(f"Verified skill '{skill_name}' with receipt {receipt['receipt_id']}")
            return {"skill": skill_name, "receipt": receipt["receipt_id"],
                    "passed": True, "writeback_id": writeback_id}

        err_text = (proc.stderr or proc.stdout or "verification failed")[:220]
        self.store.update_task(
            task["task_id"],
            status="FAILED_WITH_RECOVERY_STATE",
            verification_summary={"passed": False, "receipt_id": receipt["receipt_id"], "error": err_text},
            artifacts=[str(target_p)],
        )
        self.store.record_gap(
            source_task_id=task["task_id"],
            error_type=f"{learning_kind.upper()}_VERIFICATION_FAILED",
            missing_skill_or_tool=skill_name,
            description_id=f"Verifikasi gagal pada {item['title']}: {err_text}",
            reproduction_ref=str(target_p),
            resolution_strategy="self_repair",
        )
        self.store.emit_event(
            kind="skill_learned",
            status="FAILED",
            summary_code=f"Latihan Gagal Verifikasi: {item['title']}",
            verification_passed=False,
            artifact_refs=[str(target_p)],
            technical_detail={"skill_name": skill_name, "learning_kind": learning_kind, "error": err_text},
        )
        return {"skill": skill_name, "receipt": receipt["receipt_id"], "passed": False}

    def _writeback_verified_event(
        self,
        *,
        skill_name: str,
        title: str,
        receipt: dict[str, Any],
        learning_kind: str,
    ) -> str | None:
        """Write one externally verified event into cognitive memory.

        The event qualifies for the closed write-set as
        `skill_verified` because the receipt is external
        verification: it records the executed artifact, its exit
        code, the checked stdout and `verified_by`. The receipt
        itself is the anchored evidence. Fail-soft by design (the
        helper returns None on failure); a memory problem never
        blocks or falsifies the cycle's own verdict.
        """
        try:
            from ace_operational.memory_writeback import (
                record_verified_event,
            )

            evidence = json.dumps(
                receipt, sort_keys=True, ensure_ascii=False,
            ).encode("utf-8")
            return record_verified_event(
                self.workspace / "cognitive_memory",
                event="skill_verified",
                summary=(
                    f"skill_verified: {skill_name} "
                    f"({title}) receipt {receipt['receipt_id']}"
                ),
                evidence_bytes=evidence,
                content_extra={
                    "skill_name": skill_name,
                    "title_id": title,
                    "learning_kind": learning_kind,
                    "receipt_id": receipt["receipt_id"],
                },
            )
        except Exception:
            logger.warning(
                "skill_verified write-back failed for %s",
                skill_name, exc_info=True)
            return None

    def _writeback_skill_verified(
        self,
        *,
        item: dict[str, Any],
        receipt: dict[str, Any],
        learning_kind: str,
    ) -> str | None:
        """Write a passed curriculum verification into cognitive memory.

        The write path (ace_operational.memory_writeback) was wired
        at ratification points and at the skills expander's receipt
        issuance (EVO 0009 milestone 5), but the autonomous engine's
        own verified curriculum passes never reached the store: the
        live store held only the two operator seed records while
        the engine accumulated verified receipts (diagnosis
        2026-11-19).
        """
        return self._writeback_verified_event(
            skill_name=item["skill_name"],
            title=item["title"],
            receipt=receipt,
            learning_kind=learning_kind,
        )

    def _practice_backend_ready(self, organ: str) -> bool:
        """Whether a generative practice path may run this cycle.

        Bridge mode (EVO 0009): the brain bridge replaces the
        retired local GGUF slate, so readiness is the bridge's
        health for the role's organ. Local mode keeps the original
        rule: the local GGUF server must be healthy.
        """
        from ace_operational import brain_endpoints

        if brain_endpoints.bridge_mode():
            return brain_endpoints.health(organ)
        hc = self.models.health_check()
        return bool(hc.get("local_gguf", {}).get("server_healthy"))

    def _gen_text(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        organ: str,
    ) -> dict[str, Any] | None:
        """One generation for the dynamic practice paths.

        Bridge mode routes through brain_endpoints.chat (the role
        is the organ; the serving organ returns as
        brain_of_origin). A bridge transport failure — unhealthy
        bridge, governor budget exhausted, provider error —
        returns None: the caller treats it as "no practice this
        cycle", exactly like the local health gate, instead of
        recording a false learning failure. Local mode delegates
        to ModelRouter.generate_text unchanged.
        """
        from ace_operational import brain_endpoints

        if brain_endpoints.bridge_mode():
            try:
                result = brain_endpoints.chat(
                    organ, messages, max_tokens=max_tokens,
                    temperature=temperature, timeout=180.0)
            except brain_endpoints.BrainUnavailable as exc:
                self._bridge_transport_failures += 1
                logger.debug(
                    f"Bridge generation unavailable ({organ}): {exc}")
                return None
            return {
                "text": result.content,
                "backend_used": (
                    f"bridge:{result.brain_of_origin or organ}"),
            }
        return self.models.generate_text(
            messages, max_tokens=max_tokens, temperature=temperature)

    def execute_continuous_language_learning(self) -> dict[str, Any] | None:
        """Continuously learn Indonesian language modules, grammar, and dialogue."""
        speech_res = self._ensure_developmental_speech_skill()
        if speech_res is not None:
            return speech_res

        existing_skills = {s["name"]: s for s in self.store.list_skills()}
        for item in LANGUAGE_CURRICULUM:
            if item["skill_name"] not in existing_skills:
                return self._run_verified_curriculum_item(
                    item,
                    learning_kind="language_curriculum",
                    category="bahasa",
                    verified_by="autonomous_language_curriculum_verifier",
                    task_prefix="Belajar Bahasa",
                )

        return self._generate_dynamic_language_dialogue_practice()

    def execute_continuous_technical_learning(self) -> dict[str, Any] | None:
        """Continuously learn verified Python algorithms, AST audits, ETL, finance, and bug repair."""
        existing_skills = {s["name"]: s for s in self.store.list_skills()}
        for item in TECHNICAL_CURRICULUM:
            if item["skill_name"] not in existing_skills:
                return self._run_verified_curriculum_item(
                    item,
                    learning_kind="technical_curriculum",
                    category="engineering",
                    verified_by="autonomous_technical_curriculum_verifier",
                    task_prefix="Belajar Teknis",
                )

        return self._generate_dynamic_technical_practice()

    def execute_continuous_mixed_learning(self) -> dict[str, Any] | None:
        """Interleave technical engineering and Indonesian language tracks across cycles."""
        speech_res = self._ensure_developmental_speech_skill()
        if speech_res is not None:
            return {"track": "language_speech", **speech_res}

        if self.cycle_count % 2 == 1:
            res = self.execute_continuous_technical_learning()
            track = "technical"
            if res is None:
                res = self.execute_continuous_language_learning()
                track = "language"
        else:
            res = self.execute_continuous_language_learning()
            track = "language"
            if res is None:
                res = self.execute_continuous_technical_learning()
                track = "technical"
        return {"track": track, **(res or {})} if res is not None else {"track": track, "status": "idle"}

    @staticmethod
    def _extract_python_code(raw_text: str) -> str:
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", raw_text or "", flags=re.DOTALL)
        return match.group(1).strip() if match else (raw_text or "").strip()

    @staticmethod
    def _has_real_assert(code_text: str) -> bool:
        try:
            tree = ast.parse(code_text)
        except SyntaxError:
            return False
        return any(isinstance(node, ast.Assert) for node in ast.walk(tree))

    def _verify_python_script(self, script_path: Path, code_text: str, goal: str, loop: CodingAgentLoop) -> dict[str, Any]:
        syntax_ok, ast_err = loop._validate_and_audit_ast(code_text, goal)
        if not syntax_ok:
            return {"passed": False, "exit_code": -1, "stdout": "", "stderr": ast_err}
        if not self._has_real_assert(code_text):
            return {"passed": False, "exit_code": -1, "stdout": "", "stderr": "Skrip wajib menyertakan minimal satu assert uji nyata."}
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(code_text, encoding="utf-8")
        comp = subprocess.run([sys.executable, "-m", "py_compile", str(script_path)], capture_output=True, text=True, timeout=10)
        if comp.returncode != 0:
            return {"passed": False, "exit_code": comp.returncode, "stdout": comp.stdout, "stderr": comp.stderr or "py_compile failed"}
        try:
            proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            return {"passed": False, "exit_code": -1, "stdout": "", "stderr": "Eksekusi skrip melampaui batas 10 detik"}
        passed = proc.returncode == 0 and bool(proc.stdout.strip())
        err_msg = proc.stderr.strip() or ("" if passed else "Skrip selesai tanpa output verifikasi stdout")
        return {"passed": passed, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": err_msg}

    def _generate_dynamic_technical_practice(self) -> dict[str, Any] | None:
        """Generate, AST-check, compile, execute, and repair a Python challenge.

        The generating brain is the local GGUF slate in local mode
        or the brain bridge's coder role in bridge mode (EVO 0009);
        with neither serving, the cycle idles (returns None) and
        records nothing.
        """
        if not self._practice_backend_ready("coder"):
            return None

        cursor = self._tech_cursor
        theme = TECH_PRACTICE_THEMES[cursor % len(TECH_PRACTICE_THEMES)]
        recent_challenges = self._read_recent_jsonl_field(self.tech_corpus_file, "challenge", limit=6)
        challenge = self._pick_or_generate_challenge(theme, cursor, recent_challenges)
        self._tech_cursor += 1
        self._persist_cursors()

        coding_loop = CodingAgentLoop(self.store)
        script_path = self.workspace / "projects" / "learning_lab" / "teknis" / f"practice_cycle_{self.cycle_count}.py"
        gen_prompt = (
            f"Buat satu skrip Python 3 lengkap dan mandiri (hanya stdlib Python) untuk latihan teknis:\n"
            f"{challenge}\n\n"
            f"Syarat wajib:\n"
            f"1. Definisikan fungsi dengan logika nyata dan penanganan edge-case (nol/kosong/input invalid).\n"
            f"2. Di blok if __name__ == '__main__': jalankan minimal 2 statement assert yang benar-benar menguji fungsi.\n"
            f"3. Akhiri dengan print('TECH_PRACTICE_VERIFIED_OK').\n"
            f"4. Jangan pakai input(), eval(), exec(), atau pustaka eksternal. Keluarkan HANYA blok kode ```python ... ```."
        )
        history: list[dict[str, str]] = [{"role": "user", "content": gen_prompt}]
        code_text = ""
        ver: dict[str, Any] = {"passed": False, "exit_code": -1, "stdout": "", "stderr": "Belum dijalankan"}

        for attempt in range(2):
            gen_res = self._gen_text(
                history, max_tokens=512, temperature=0.15, organ="coder")
            if gen_res is None:
                # Bridge transport failure: idle without recording
                # a practice task or a false learning failure.
                return None
            raw_reply = str((gen_res or {}).get("text", ""))
            history.append({"role": "assistant", "content": raw_reply})
            code_text = self._extract_python_code(raw_reply)
            ver = self._verify_python_script(script_path, code_text, challenge, coding_loop)
            if ver["passed"] or attempt == 1:
                break
            history.append({
                "role": "user",
                "content": (
                    f"Skrip sebelumnya gagal verifikasi ({ver['stderr'][:280]}). "
                    f"Perbaiki skrip Python 3 tersebut agar lolos AST audit, py_compile, dan seluruh assert. "
                    f"Keluarkan HANYA blok kode ```python ... ```."
                ),
            })

        task = self.store.create_task(
            title_id=f"Latihan Teknis #{self.cycle_count}: {challenge[:48]}",
            user_request=challenge,
            normalized_goal=challenge,
        )
        self.store.update_task(task["task_id"], status="ACTIVE")
        receipt = self.store.record_receipt(
            task_id=task["task_id"],
            action_kind="execute_dynamic_technical_practice",
            input_data=code_text or challenge,
            output_data=ver["stdout"],
            command_or_operation=f"{sys.executable} {script_path}",
            exit_code=int(ver["exit_code"]),
            stdout_text=ver["stdout"],
            stderr_text=ver["stderr"],
            artifacts_created=[str(script_path)] if script_path.exists() else [],
            verified_by="autonomous_technical_practice_verifier",
            passed=bool(ver["passed"]),
        )
        if ver["passed"]:
            self.store.update_task(
                task["task_id"],
                status="COMPLETED",
                verification_summary={"passed": True, "receipt_id": receipt["receipt_id"]},
                artifacts=[str(script_path)],
            )
            with open(self.tech_corpus_file, "a", encoding="utf-8") as fp:
                fp.write(json.dumps({
                    "cycle": self.cycle_count,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "theme": theme,
                    "challenge": challenge,
                    "script_path": str(script_path),
                    "receipt_id": receipt["receipt_id"],
                }, ensure_ascii=False) + "\n")
            self.store.emit_event(
                kind="test_executed",
                status="COMPLETED",
                summary_code=f"Latihan Teknis Terverifikasi: {challenge[:42]}",
                verification_passed=True,
                artifact_refs=[str(script_path)],
                technical_detail={
                    "title_id": f"Latihan Teknis #{self.cycle_count}",
                    "challenge": challenge,
                    "receipt_id": receipt["receipt_id"],
                    "stdout_preview": ver["stdout"].strip()[:80],
                },
            )
            writeback_id = self._writeback_verified_event(
                skill_name=f"tech_practice::{theme[:48]}",
                title=f"Latihan Teknis: {theme}",
                receipt=receipt,
                learning_kind="dynamic_technical_practice",
            )
            return {"technical_practice": challenge, "script": str(script_path), "passed": True, "receipt": receipt["receipt_id"], "writeback_id": writeback_id}

        self.store.update_task(
            task["task_id"],
            status="FAILED_WITH_RECOVERY_STATE",
            verification_summary={"passed": False, "receipt_id": receipt["receipt_id"], "error": ver["stderr"][:200]},
            artifacts=[str(script_path)] if script_path.exists() else [],
        )
        self.store.record_gap(
            source_task_id=task["task_id"],
            error_type="DYNAMIC_TECH_PRACTICE_FAILED",
            missing_skill_or_tool=f"tech_practice::{theme[:36]}",
            description_id=f"Latihan teknis gagal setelah repair untuk '{challenge[:80]}': {ver['stderr'][:180]}",
            reproduction_ref=str(script_path),
            resolution_strategy="self_repair",
        )
        self.store.emit_event(
            kind="test_executed",
            status="FAILED",
            summary_code=f"Latihan Teknis Gagal: {challenge[:42]}",
            verification_passed=False,
            artifact_refs=[str(script_path)] if script_path.exists() else [],
            technical_detail={"failure_hint": ver["stderr"][:140], "challenge": challenge},
        )
        return {"technical_practice": challenge, "script": str(script_path), "passed": False, "receipt": receipt["receipt_id"]}

    def _read_recent_jsonl_field(self, path: Path, field: str, limit: int = 6) -> list[str]:
        if not path.exists():
            return []
        values: list[str] = []
        try:
            for raw in path.read_text(encoding="utf-8").splitlines()[-limit:]:
                if raw.strip():
                    values.append(str(json.loads(raw).get(field, "")))
        except (OSError, ValueError) as exc:
            logger.debug(f"Could not read recent entries from {path}: {exc}")
        return values

    def _pick_or_generate_challenge(self, theme: str, cursor: int, recent_challenges: list[str]) -> str:
        fallback_challenges = [
            "Implementasikan algoritma deteksi siklus pada graf dependensi berarah beserta uji asersi graf siklik dan asiklik.",
            "Buat parser konfigurasi key=value tahan komentar dan baris rusak serta uji kasus valid dan kosong.",
            "Implementasikan LRU Cache berkapasitas tetap dengan get/put dan uji urutan eviction dengan assert.",
            "Buat fungsi penghitung pajak progresif dan diskon bertingkat dengan penjagaan nilai negatif serta assert.",
            "Buat detektor AST untuk melarang eval/exec pada kode sumber Python beserta pengujian kasus bersih dan terlarang.",
        ]
        try:
            avoid_note = (
                f" Hindari mengulang topik mirip: {'; '.join(c[:50] for c in recent_challenges[-3:] if c)}."
                if recent_challenges
                else ""
            )
            gen_q = self._gen_text([
                {
                    "role": "system",
                    "content": "Buat tepat SATU spesifikasi tantangan coding Python singkat (12-28 kata) tanpa kode atau penjelasan tambahan.",
                },
                {"role": "user", "content": f"Tema teknis #{cursor}: {theme}.{avoid_note}"},
            ], max_tokens=80, temperature=0.7, organ="coder")
            cand = str((gen_q or {}).get("text", "")).strip().strip("\"'")
            if 18 <= len(cand) <= 240 and cand not in recent_challenges:
                return cand
        except Exception as exc:
            logger.debug(f"Dynamic challenge prompt generation fallback: {exc}")
        return fallback_challenges[cursor % len(fallback_challenges)]

    def _generate_dynamic_language_dialogue_practice(self) -> dict[str, Any] | None:
        """Generate and evaluate real-time Indonesian dialogue interactions.

        The generating brain is the local GGUF slate in local mode
        or the brain bridge's front role in bridge mode (EVO 0009);
        with neither serving, the cycle idles (returns None).
        """
        if not self._practice_backend_ready("front"):
            return None

        themes = [
            "kosakata Indonesia yang jarang dipakai namun indah beserta contoh kalimatnya",
            "idiom atau ungkapan khas Indonesia dan maknanya dalam percakapan",
            "perbedaan nuansa dua kata sinonim dalam bahasa Indonesia",
            "penggunaan imbuhan me-kan vs me-i dengan contoh nyata",
            "ragam bahasa santai anak muda Indonesia vs padanan bakunya",
            "kosakata seputar alam, cuaca, dan suasana senja di Indonesia",
            "etika bertutur kata yang halus saat menolak atau mengkritik di tempat kerja",
            "istilah kuliner atau tradisi Nusantara beserta artinya",
            "peribahasa Indonesia beserta pelajaran praktisnya",
            "padanan kata Indonesia yang tepat untuk istilah teknologi sehari-hari",
            "konsep pemrograman dasar (fungsi, variabel, loop, debugging) dijelaskan dengan bahasa Indonesia santai",
            "perbandingan kegunaan bahasa pemrograman seperti Python, JavaScript, atau SQL dalam proyek nyata",
            "cara menjelaskan masalah teknis atau bug kode ke rekan kerja non-teknis dengan jelas",
            "produktivitas kerja, manajemen waktu, dan komunikasi efektif di tim atau proyek",
            "literasi finansial pribadi: menabung, dana darurat, anggaran bulanan, dan menghindari utang konsumtif",
            "istilah keuangan dan bisnis (arus kas, modal, margin, investasi, inflasi) dalam bahasa sederhana",
            "kebiasaan baik saat menulis kode yang rapi, mudah dibaca, dan tahan error",
            "pengambilan keputusan praktis saat menghadapi deadline ketat atau prioritas yang bentrok",
            "obrolan kasual sehari-hari tentang hobi, buku, musik, atau cara melepas penat",
            "cara berpikir terstruktur untuk memecahkan masalah rumit menjadi langkah-langkah kecil",
        ]
        cursor = self._lang_cursor
        theme = themes[cursor % len(themes)]
        recent_prompts = self._read_recent_jsonl_field(self.corpus_file, "prompt", limit=6)

        prompt = ""
        try:
            avoid_note = (
                f" Hindari mengulang topik yang mirip dengan: {'; '.join(p[:60] for p in recent_prompts[-3:] if p)}."
                if recent_prompts
                else ""
            )
            gen_q = self._gen_text(
                [
                    {
                        "role": "system",
                        "content": (
                            "Buat tepat SATU pertanyaan diskusi atau latihan bahasa Indonesia yang singkat (10-24 kata), "
                            "spesifik, dan menarik sesuai tema. Tulis pertanyaannya saja tanpa pengantar atau tanda kutip."
                        ),
                    },
                    {"role": "user", "content": f"Tema latihan #{cursor}: {theme}.{avoid_note}"},
                ],
                max_tokens=70,
                temperature=0.8,
                organ="front",
            )
            candidate_q = str((gen_q or {}).get("text", "")).strip().strip("\"'")
            if 15 <= len(candidate_q) <= 220 and candidate_q not in recent_prompts:
                prompt = candidate_q
        except Exception as exc:
            logger.debug(f"Dynamic dialogue prompt fallback: {exc}")

        if not prompt:
            fallback_prompts = [
                "Jelaskan arti ungkapan 'ringan tangan' dan berikan satu contoh kalimatnya.",
                "Apa bedanya kata 'melihat', 'memandang', dan 'menatap' dalam bahasa Indonesia?",
                "Sebutkan tiga kata serapan bahasa Indonesia dari bahasa daerah beserta artinya.",
                "Bagaimana cara menggunakan imbuhan 'ber-an' yang benar dalam kalimat sehari-hari?",
                "Berikan contoh kalimat dengan kata 'temaram' dan jelaskan nuansanya.",
            ]
            prompt = fallback_prompts[cursor % len(fallback_prompts)]

        self._lang_cursor += 1
        self._persist_cursors()
        logger.info(f"[Continuous Language Learning] Exploring dynamic dialogue: '{prompt}'...")

        try:
            resp = self._gen_text([
                {"role": "system", "content": "Kamu adalah ACE, entitas kecerdasan otonom yang mendalami bahasa Indonesia. Berikan jawaban yang bernas, santai, dan tepat bahasa."},
                {"role": "user", "content": prompt},
            ], max_tokens=200, temperature=0.2, organ="front")
            ans = (resp or {}).get("text", "").strip()
            if ans:
                try:
                    SpeechDevelopmentEngine(self.store).observe_user_utterance(ans)
                except Exception as exc:
                    logger.debug(f"Dialogue lexicon observe skipped: {exc}")

                entry = {
                    "cycle": self.cycle_count,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "theme": theme,
                    "prompt": prompt,
                    "response": ans,
                    "backend": resp.get("backend_used", "local-gguf"),
                }
                with open(self.corpus_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                self.store.emit_event(
                    kind="test_executed",
                    status="COMPLETED",
                    summary_code=f"Latihan Dialog Bahasa: {prompt[:35]}...",
                    verification_passed=True,
                    technical_detail={
                        "title_id": "Latihan Dialog Bahasa Indonesia Otomatis",
                        "prompt": prompt,
                        "sample_answer": ans[:80],
                    },
                )
                return {"dialogue_practice": prompt, "answer_preview": ans[:40]}
        except Exception as e:
            logger.warning(f"Dynamic language practice failed: {e}")
        return None

    def _resolve_word_meaning(
        self,
        speech_engine: SpeechDevelopmentEngine,
        word: str,
        known_roots: set[str],
    ) -> tuple[str, str, str] | None:
        std = COLLOQUIAL_SLANG_MAP.get(word)
        if std:
            base = speech_engine.lookup_word(std, allow_fuzzy=False)
            if base:
                return f"bentuk santai dari '{std}' ({base['meaning_id']})", str(base.get("role") or ""), "auto_slang"

        base_exact = speech_engine.lookup_word(word, allow_fuzzy=False)
        if base_exact and base_exact.get("word") != word:
            return (
                f"bentuk dari '{base_exact['word']}' ({base_exact['meaning_id']})",
                str(base_exact.get("role") or ""),
                "auto_morphology",
            )

        morph = analyze_morphology(word, known_roots=known_roots)
        root = str(morph.get("root") or "")
        if root and root != word:
            base = speech_engine.lookup_word(root, allow_fuzzy=False)
            if base:
                return (
                    f"bentuk berimbuhan dari '{root}' ({base['meaning_id']})",
                    str(morph.get("pos_hint") or base.get("role") or ""),
                    "auto_morphology",
                )

        if self._practice_backend_ready("front"):
            resp = self._gen_text(
                [
                    {"role": "system", "content": "Jawab hanya arti singkat kata Bahasa Indonesia dalam 3-8 kata tanpa tanda kutip."},
                    {"role": "user", "content": f"Apa arti kata '{word}' dalam Bahasa Indonesia?"},
                ],
                max_tokens=40,
                temperature=0.2,
                organ="front",
            )
            ans = str((resp or {}).get("text", "")).strip().strip(".\"' ")
            if 3 <= len(ans) <= 120:
                origin = (
                    "auto_bridge"
                    if str((resp or {}).get("backend_used", "")).startswith("bridge:")
                    else "auto_gguf"
                )
                return ans, "", origin
        return None

    def _explore_vocabulary_batch(self, batch_size: int = 25) -> list[dict[str, Any]]:
        """Actively harvest and ground a batch of new Indonesian vocabulary.

        The generating brain is the local GGUF slate in local mode
        or the brain bridge's front role in bridge mode (EVO 0009).
        """
        if not self._practice_backend_ready("front"):
            return []

        domains = [
            "peralatan rumah tangga dan dapur",
            "tumbuhan, bunga, dan pepohonan",
            "hewan darat, laut, dan burung",
            "makanan tradisional dan jajanan pasar",
            "kata sifat tentang watak dan kepribadian",
            "kata kerja gerakan tangan dan tubuh",
            "cuaca, langit, sungai, dan pegunungan",
            "pakaian, kain, dan aksesori",
            "alat musik, tarian, dan kesenian daerah",
            "kendaraan, jalanan, dan perjalanan",
            "kesehatan, bagian tubuh, dan pengobatan",
            "perdagangan, pasar, dan keuangan",
            "pemrograman, algoritma, dan pengembangan perangkat lunak",
            "jaringan komputer, server, keamanan, dan basis data",
            "dunia kerja, kantor, manajemen proyek, dan kolaborasi tim",
            "finansial, akuntansi, investasi, pajak, dan perbankan",
            "hukum, aturan, kontrak, dan administrasi",
            "logika, analisis masalah, riset, dan pengambilan keputusan",
        ]
        letters = "abcdefghjklmnprstw"
        domain = domains[self._lang_cursor % len(domains)]
        start_letter = letters[self._lang_cursor % len(letters)]

        speech_engine = SpeechDevelopmentEngine(self.store)
        known_words = {str(w.get("word", "")).lower() for w in speech_engine.list_lexicon() if w.get("word")}

        resp = self._gen_text(
            [
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah kamus Bahasa Indonesia. Tulis daftar kata tunggal (1 kata alfabet, minimal 4 huruf) "
                        "beserta arti singkatnya (3-7 kata). Contoh format:\n"
                        "sendok: alat makan untuk menyendok kuah\n"
                        "angin: udara yang bergerak di alam\n"
                        "ramah: bersikap baik dan mudah bergaul"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Tuliskan {batch_size} kata Bahasa Indonesia bertema {domain} "
                        f"(utamakan awalan huruf '{start_letter}' atau sekitarnya), masing-masing di baris baru "
                        "dengan format `kata: arti singkat` tanpa penjelasan tambahan."
                    ),
                },
            ],
            max_tokens=560,
            temperature=0.85,
            organ="front",
        )
        batch_source = (
            "auto_bridge_batch"
            if str((resp or {}).get("backend_used", "")).startswith("bridge:")
            else "auto_gguf_batch"
        )
        raw_text = str((resp or {}).get("text", "")).strip()
        if not raw_text:
            return []

        learned: list[dict[str, Any]] = []
        for line in raw_text.splitlines():
            cleaned = line.strip().lstrip("-*•0123456789. )")
            sep = ":" if ":" in cleaned else (" - " if " - " in cleaned else "")
            if not sep:
                continue
            word_part, meaning_part = cleaned.split(sep, 1)
            word = word_part.strip().strip("\"'`* ").lower()
            meaning_id = meaning_part.replace("**", "").strip().strip(".\"'* ")
            if not word.isalpha() or len(word) < 4 or word in known_words:
                continue
            if not (3 <= len(meaning_id) <= 120):
                continue
            res = speech_engine.teach_word(word, meaning_id, role="")
            if res.get("accepted"):
                known_words.add(word)
                learned.append({"word": word, "meaning_id": meaning_id, "source": batch_source})

        if learned:
            samples = [item["word"] for item in learned[:6]]
            self.store.emit_event(
                kind="skill_learned",
                status="COMPLETED",
                summary_code=f"Eksplorasi kosakata ({len(learned)} kata baru): {domain}",
                verification_passed=True,
                technical_detail={
                    "skill_name": f"kosakata_tema_{self.cycle_count}",
                    "learning_kind": "vocab_batch",
                    "domain": domain,
                    "count": len(learned),
                    "sample_words": samples,
                    "source": batch_source,
                },
            )
            logger.info(
                f"[Vocab Batch] Grounded {len(learned)} new words ({domain[:28]}...): "
                f"{', '.join(samples)}"
            )
        return learned

    def _auto_teach_heard_words(self, limit: int = 30) -> list[dict[str, Any]]:
        """Automatically ground newly encountered Indonesian words during auto-run cycles."""
        speech_engine = SpeechDevelopmentEngine(self.store)
        ungrounded = speech_engine.list_heard_words(ungrounded_only=True, limit=limit)
        if not ungrounded:
            return []
        known_roots = {str(w.get("word", "")).lower() for w in speech_engine.list_lexicon() if w.get("word")}
        learned: list[dict[str, Any]] = []
        need_gguf: list[str] = []

        for item in ungrounded:
            word = str(item.get("word", "")).strip().lower()
            if not word:
                continue
            std = COLLOQUIAL_SLANG_MAP.get(word)
            resolved: tuple[str, str, str] | None = None
            if std:
                base = speech_engine.lookup_word(std, allow_fuzzy=False)
                if base:
                    resolved = (f"bentuk santai dari '{std}' ({base['meaning_id']})", str(base.get("role") or ""), "auto_slang")
            if resolved is None:
                base_exact = speech_engine.lookup_word(word, allow_fuzzy=False)
                if base_exact and base_exact.get("word") != word:
                    resolved = (f"bentuk dari '{base_exact['word']}' ({base_exact['meaning_id']})", str(base_exact.get("role") or ""), "auto_morphology")
            if resolved is None:
                morph = analyze_morphology(word, known_roots=known_roots)
                root = str(morph.get("root") or "")
                if root and root != word:
                    base = speech_engine.lookup_word(root, allow_fuzzy=False)
                    if base:
                        resolved = (f"bentuk berimbuhan dari '{root}' ({base['meaning_id']})", str(morph.get("pos_hint") or base.get("role") or ""), "auto_morphology")
            if resolved is not None:
                meaning_id, role, origin = resolved
                res = speech_engine.teach_word(word, meaning_id, role=role)
                if res.get("accepted"):
                    known_roots.add(word)
                    learned.append({"word": word, "meaning_id": meaning_id, "source": origin})
                    logger.info(f"[Auto-Teach] Grounded new word '{word}' ({origin}): {meaning_id}")
            else:
                need_gguf.append(word)

        if need_gguf:
            if self._practice_backend_ready("front"):
                resp = self._gen_text(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Jelaskan arti singkat (3-8 kata) setiap kata Bahasa Indonesia berikut. "
                                "Format WAJIB satu baris per kata: `kata: arti singkat` tanpa nomor."
                            ),
                        },
                        {"role": "user", "content": ", ".join(need_gguf)},
                    ],
                    max_tokens=max(120, len(need_gguf) * 24),
                    temperature=0.2,
                    organ="front",
                )
                gguf_origin = (
                    "auto_bridge"
                    if str((resp or {}).get("backend_used", "")).startswith("bridge:")
                    else "auto_gguf"
                )
                for line in str((resp or {}).get("text", "")).splitlines():
                    cleaned = line.strip().lstrip("-*•0123456789. ")
                    if ":" not in cleaned:
                        continue
                    w_part, m_part = cleaned.split(":", 1)
                    w_clean = w_part.strip().strip("\"'`* ").lower()
                    m_clean = m_part.replace("**", "").strip().strip(".\"'* ")
                    if w_clean in need_gguf and 3 <= len(m_clean) <= 120:
                        res = speech_engine.teach_word(w_clean, m_clean, role="")
                        if res.get("accepted"):
                            known_roots.add(w_clean)
                            learned.append({"word": w_clean, "meaning_id": m_clean, "source": gguf_origin})
                            logger.info(f"[Auto-Teach] Grounded new word '{w_clean}' ({gguf_origin}): {m_clean}")
        return learned

    def _run_periodic_self_evolution_audit(self) -> dict[str, Any] | None:
        """Run a lightweight AST health audit on internal modules every 10th cycle."""
        try:
            evo = SelfEvolutionEngine(self.store, self.models)
            audit = evo.audit_internal_codebase()
            passed = bool(audit.get("codebase_clean"))
            self.store.emit_event(
                kind="test_executed",
                status="COMPLETED" if passed else "FAILED",
                summary_code="Audit AST Kodebase Internal",
                verification_passed=passed,
                technical_detail={
                    "title_id": "Audit Integritas AST Kodebase ACE",
                    "total_python_files": audit.get("total_python_files"),
                    "total_lines_of_code": audit.get("total_lines_of_code"),
                    "syntax_errors_count": audit.get("syntax_errors_count"),
                },
            )
            return audit
        except Exception as exc:
            logger.warning(f"Periodic AST audit failed: {exc}")
            return None

    def execute_ratification_step(
        self,
        *,
        episodes_path: Path | None = None,
        memory_root: Path | None = None,
        chat_fn=None,
        pair_fn=None,
    ) -> dict[str, Any]:
        """One ratification-loop episode (EVO 0005's machine).

        Reads the next episode from the ratification source
        (workspace/projects/ratification/episodes.jsonl),
        advances the persisted cursor
        (autonomous_ratification_cursor, the same store-meta
        pattern as the other cursors), runs it through
        ace_operational.ratification_loop, and emits a store
        event. A ratified episode is written back into
        cognitive memory by the loop itself. Missing source
        and an exhausted source are clean no-ops, so the
        cycle can call this step unconditionally once
        enabled."""
        from ace_operational import ratification_loop

        source = episodes_path or (
            self.workspace / "projects" / "ratification"
            / "episodes.jsonl")
        if not source.exists():
            return {"status": "no_source", "source": str(source)}
        episodes = ratification_loop.load_episodes(source)
        cursor = self._load_int_meta(
            "autonomous_ratification_cursor", 0)
        if cursor >= len(episodes):
            return {"status": "exhausted", "cursor": cursor,
                    "episodes": len(episodes)}
        episode = episodes[cursor]
        result = ratification_loop.run_ratification_episode(
            episode,
            memory_root=memory_root
            or (self.workspace / "cognitive_memory"),
            chat_fn=chat_fn, pair_fn=pair_fn)
        self.store.set_meta("autonomous_ratification_cursor",
                            str(cursor + 1))
        self.store.emit_event(
            kind="ratification_episode",
            status="COMPLETED" if result.get("ratified")
            else "FAILED",
            summary_code=f"Ratifikasi: {episode['id']}",
            verification_passed=bool(result.get("ratified")),
            technical_detail={
                "episode_id": episode["id"],
                "task_kind": episode["task_kind"],
                "ratified": bool(result.get("ratified")),
                "writeback_id": result.get("writeback_id"),
                "error": result.get("error")})
        return {"status": "measured", "cursor": cursor,
                "episode_id": episode["id"],
                "ratified": bool(result.get("ratified")),
                "writeback_id": result.get("writeback_id")}

    def execute_director_step(self) -> dict[str, Any]:
        """Masukkan satu usulan berprovenance ke agenda untuk ditelaah."""
        from ace_operational import brain_endpoints, director_loop, director_strong

        if not brain_endpoints.bridge_mode():
            raise brain_endpoints.BrainUnavailable("Jalur director memerlukan brain bridge.")
        observation = director_loop.build_observation(
            gates={},
            gaps=[{"id": gap["gap_id"]} for gap in self.store.list_gaps(status="OPEN")[:20]],
            results=[
                {"id": item["deliverable_id"], "status": item["status"]}
                for item in self.store.list_deliverables()
            ],
            memory_facts=(
                [{"receipt_context": self._director_context_block}]
                if getattr(self, "_director_context_block", None) else None
            ),
        )
        origin = ""

        def infer(prompt: str) -> str:
            nonlocal origin
            reply = brain_endpoints.chat_structured(
                "front", [{"role": "user", "content": prompt}],
                max_tokens=768, check_health=False,
            )
            provider, _, model = reply.brain_of_origin.partition("/")
            origin = director_strong.brain_of_origin(provider, model)
            return reply.content

        proposal = director_loop.request_direction(observation, infer)
        if not origin:
            raise director_loop.ProposalRejected("Arahan tidak memiliki asal organ.")
        # Dedupe (gelombang robustness 2026-11-20): director mengusulkan
        # tiap siklus dari observasi yang sama, jadi tanpa pemeriksa ini
        # agenda menumpuk duplikat WAITING untuk gap yang sama (38 tugas
        # dalam ~80 menit pada malam aktivasi). Satu proposal terbuka per
        # fakta based_on sudah cukup untuk ditelaah.
        based_on = {str(b) for b in proposal.get("based_on") or []}
        if based_on:
            for existing in self.store.list_tasks(limit=200):
                if existing.get("kind") != "director_proposal":
                    continue
                if existing.get("status") != "WAITING_FOR_DEPENDENCY":
                    continue
                other = (existing.get("checkpoint") or {}).get("proposal") or {}
                if based_on & {str(b) for b in other.get("based_on") or []}:
                    return {"status": "duplicate_skipped",
                            "task_id": existing["task_id"],
                            "title": proposal["title"],
                            "brain_of_origin": origin}
        task = self.store.create_task(
            kind="director_proposal",
            title_id=proposal["title"],
            user_request=proposal["rationale"],
            normalized_goal=proposal["title"],
            model_backend=origin,
            priority=proposal["score"],
            checkpoint={"stage": "director_review", "cycle": self.cycle_count,
                        "brain_of_origin": origin, "proposal": proposal},
            hold_for_review=True,
        )
        return {"status": "proposed", "task_id": task["task_id"],
                "title": proposal["title"], "brain_of_origin": origin}

    def execute_cycle(self) -> dict[str, Any]:
        """Run a single autonomous mixed cycle (agenda, technical, language, self-audit)."""
        cycle_started_at = time.monotonic()
        step_durations: list[tuple[str, float]] = []
        self.cycle_count += 1
        self._persist_cursors()
        logger.info(f"--- Starting Autonomous Cycle #{self.cycle_count} ---")
        self.update_status_file("cycle_started")

        # Step 1: Health & GGUF verification
        self.update_status_file("discovering_models")
        self.verify_and_promote_local_gguf()

        # Step 2: Advance queued agenda items
        self.update_status_file("advancing_agenda")
        step_started_at = time.monotonic()
        advanced_count = self.check_and_advance_agenda()
        step_durations.append(("advancing_agenda", time.monotonic() - step_started_at))

        # Step 3: Interleaved Technical + Indonesian Language Learning
        mixed_res: dict[str, Any] = {}
        vocab_learned: list[dict[str, Any]] = []
        if advanced_count == 0:
            self.update_status_file("mixed_autonomous_learning")
            step_started_at = time.monotonic()
            mixed_res = self.execute_continuous_mixed_learning() or {}
            track = str(mixed_res.get("track") or "")
            if track.startswith("language") and self._lang_cursor % 2 == 1:
                vocab_learned = self._explore_vocabulary_batch()
            step_durations.append(("mixed_autonomous_learning", time.monotonic() - step_started_at))
        heard_learned = self._auto_teach_heard_words()

        # Step 3b: Ratification loop (EVO 0005) — env-gated so
        # this wiring changes no live behaviour until a
        # measurement window enables it.
        ratification_res: dict[str, Any] | None = None
        if os.environ.get("ACE_RATIFICATION_LOOP") == "1":
            self.update_status_file("ratification_loop")
            step_started_at = time.monotonic()
            ratification_res = self.execute_ratification_step()
            step_durations.append(("ratification_loop", time.monotonic() - step_started_at))

        director_res = None
        if os.environ.get("ACE_DIRECTOR_LOOP") == "1":
            self.update_status_file("director_loop")
            try:
                director_res = self.execute_director_step()
            except Exception as exc:
                director_res = {"status": "error", "error": type(exc).__name__}

        # Step 3c: Eksekusi director Kelas A (EVO 0012 M2) — env-gated
        # ACE_DIRECTOR_EXEC_A; tanpa flag, perilaku live tidak berubah.
        director_exec_res = None
        if os.environ.get("ACE_DIRECTOR_EXEC_A") == "1":
            self.update_status_file("director_execution")
            try:
                from ace_operational import director_execution
                director_exec_res = director_execution.run_execution_step(
                    self.store, self.workspace)
            except Exception as exc:
                director_exec_res = {"status": "error", "error": type(exc).__name__}

        # Step 3d: Wiring lompatan EVO 0031–0040 — env-gated
        # ACE_LEAPS; tiap step fail-closed per pola Step 3c, dengan
        # throttle per step agar biaya siklus tetap kecil.
        leaps_res: dict[str, Any] = {}
        if os.environ.get("ACE_LEAPS") == "1":
            from ace_operational import leap_wiring

            def _leap(name: str, fn: Any) -> None:
                try:
                    leaps_res[name] = fn(self)
                except Exception as exc:
                    leaps_res[name] = {"status": "error",
                                       "error": type(exc).__name__}

            self.update_status_file("leap_steps")
            _leap("checkpoint", leap_wiring.step_checkpoint)
            _leap("house", leap_wiring.step_house)
            _leap("director", leap_wiring.step_director)
            _leap("practice", leap_wiring.step_practice)
            _leap("projects", leap_wiring.step_projects)
            if self.cycle_count % 10 == 0:
                _leap("recall", leap_wiring.step_recall)
            if self.cycle_count % 25 == 0:
                _leap("self", leap_wiring.step_self)
            if self.cycle_count % 200 == 1:
                _leap("organs", leap_wiring.step_organs)
            if self.cycle_count % 200 == 0:
                _leap("citation_validator", leap_wiring.step_citation_validator)

        # Step 4: Periodic AST self-audit
        audit_summary: dict[str, Any] | None = None
        if self.cycle_count % 10 == 0:
            self.update_status_file("self_evolution_audit")
            step_started_at = time.monotonic()
            audit_summary = self._run_periodic_self_evolution_audit()
            step_durations.append(("self_evolution_audit", time.monotonic() - step_started_at))

        self._persist_cursors()

        # Step 5: Sync summary
        summary = {
            "cycle": self.cycle_count,
            "track": mixed_res.get("track", "agenda" if advanced_count > 0 else "idle"),
            "advanced_agenda": advanced_count,
            "learning_result": mixed_res,
            "vocab_added": len(vocab_learned),
            "heard_grounded": len(heard_learned),
            "ratification": ratification_res,
            "self_audit": audit_summary,
        }
        if director_res is not None:
            summary["director"] = director_res
        if director_exec_res is not None:
            summary["director_execution"] = director_exec_res
        if leaps_res:
            summary["leaps"] = leaps_res
        slowest_name, slowest_seconds = max(step_durations, key=lambda step: step[1])
        self._last_cycle_duration_seconds = time.monotonic() - cycle_started_at
        self._slowest_step = {"name": slowest_name, "seconds": slowest_seconds}
        self.update_status_file("idle_waiting_next_cycle", {
            "last_cycle_completed": self.cycle_count,
            "track": summary["track"],
            "vocab_added": summary["vocab_added"],
            "next_cycle_in_seconds": self.tick_interval_seconds,
        })
        logger.info(
            f"--- Completed Autonomous Cycle #{self.cycle_count} (track={summary['track']}). "
            f"Sleeping {self.tick_interval_seconds}s ---"
        )
        return summary

    def run_forever(self) -> None:
        """Run continuous autonomous cycles indefinitely until stopped."""
        self.running = True
        logger.info("ACE Continuous Autonomous Engine starting. Press Ctrl+C or kill process to stop.")
        self.update_status_file("running")

        def handle_signal(sig, frame):
            logger.info(f"Termination signal {sig} received. Initiating graceful shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self.running:
                try:
                    self.execute_cycle()
                except Exception as e:
                    logger.error(f"Error during autonomous cycle #{self.cycle_count}: {e}", exc_info=True)
                    self.update_status_file("cycle_error", {"error": str(e)})

                slept = 0.0
                step = 0.5
                while self.running and slept < self.tick_interval_seconds:
                    time.sleep(step)
                    slept += step

        finally:
            self.running = False
            self.update_status_file("stopped")
            logger.info("ACE Continuous Autonomous Engine cleanly stopped.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ACE Continuous Mixed Autonomous Engine")
    ap.add_argument("--workspace", type=Path, default=None, help="Direktori workspace operasional ACE")
    ap.add_argument("--interval", type=float, default=6.0, help="Jeda antar siklus dalam detik (default: 6.0)")
    ap.add_argument("--once", action="store_true", help="Jalankan tepat 1 siklus lalu keluar")
    ap.add_argument("--cycles", type=int, default=0, help="Jalankan maksimal N siklus lalu keluar (0 = tanpa batas)")
    args = ap.parse_args(argv)

    engine = ContinuousAutonomousEngine(
        workspace=args.workspace,
        tick_interval_seconds=max(0.2, float(args.interval)),
    )
    if args.once:
        print(json.dumps(engine.execute_cycle(), ensure_ascii=False, indent=2))
        return 0
    if args.cycles > 0:
        out = []
        for idx in range(args.cycles):
            out.append(engine.execute_cycle())
            if idx + 1 < args.cycles and engine.tick_interval_seconds > 0:
                time.sleep(min(engine.tick_interval_seconds, 1.0))
        print(json.dumps({"cycles_executed": len(out), "results": out}, ensure_ascii=False, indent=2))
        return 0
    engine.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
