#!/usr/bin/env python3
"""Generator parameterized soal corpus `code` ACE (WS-B #4).

Menghasilkan kandidat episode berformat house JSONL:
`{id, kind, task_kind, instruction}`
dari template algoritmik berparameter dengan kombinasi kasus tepi eksplisit
dan ketentuan `"Sertakan docstring Bahasa Indonesia."`, lalu memvalidasi diri
sendiri melalui `tools.corpus_lint.lint_lines` sebelum menulis keluaran.

Catatan ketergantungan: mengimpor `tools.corpus_lint` (PR #256).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import sys
from typing import Any

from tools.corpus_lint import (
    FROZEN_PREFIX_LEN,
    InvalidInputError,
    lint_lines,
    load_frozen_prefixes,
)

FACTORY_SCHEMA = "ace.corpus-factory-code.v1"
DEFAULT_PREFIX = "code_gen_"


class CorpusFactoryCodeError(ValueError):
    """Kesalahan parameter masukan atau kegagalan menghasilkan corpus code."""


@dataclass(frozen=True)
class CodeTemplate:
    """Template algoritmik berparameter untuk episode `code`."""

    family: str
    variants: tuple[dict[str, str], ...]
    edge_case_pool: tuple[str, ...]

    def render_instruction(
        self,
        variant: dict[str, str],
        focus_phrase: str,
        edge_cases: tuple[str, ...],
        tie_rule: str,
    ) -> str:
        edges_text = "; ".join(edge_cases)
        lead = variant["lead"]
        lead_lower = lead[0].lower() + lead[1:] if lead else lead
        return (
            f"Pada kasus {focus_phrase}, {lead_lower} "
            f"Implementasikan fungsi Python `{variant['signature']}` menggunakan pustaka standar saja. "
            f"Spesifikasi inti: {variant['core']} "
            f"Aturan deterministik seri/ikatan: {tie_rule} "
            f"Tangani secara eksplisit kasus tepi berikut: {edges_text}. "
            f"Kembalikan {variant['returns']} dan naikkan `ValueError` untuk masukan tidak valid. "
            f"Sertakan docstring Bahasa Indonesia."
        )


CODE_TEMPLATES: tuple[CodeTemplate, ...] = (
    CodeTemplate(
        family="interval_scheduler",
        variants=(
            {
                "lead": "Jadwalkan pemakaian ruang rapat berkapasitas tunggal agar total durasi rapat terbobot maksimum tanpa tumpang tindih.",
                "signature": "jadwalkan_ruang_optimal(daftar_rapat)",
                "core": "setiap item berupa tuple (id_rapat, mulai, selesai, bobot) dengan interval setengah-terbuka [mulai, selesai).",
                "returns": "tuple (total_bobot, daftar_id_terpilih) terurut menurut waktu mulai",
            },
            {
                "lead": "Gabungkan rentang waktu pemeliharaan server yang saling bersentuhan atau bertumpuk sekaligus hitung total menit aktif.",
                "signature": "konsolidasi_jendela_rawat(jendela_list)",
                "core": "setiap item berupa tuple (mulai_menit, selesai_menit) dan interval berdampingan [a, b) + [b, c) harus digabung.",
                "returns": "tuple (daftar_interval_gabungan, total_durasi_menit)",
            },
            {
                "lead": "Hitung jumlah minimum pekerja paralel yang diperlukan untuk menyelesaikan seluruh antrean pekerjaan berinterval waktu.",
                "signature": "hitung_slot_minimum(pekerjaan)",
                "core": "setiap item berupa dict {id, start, end} dan dua pekerjaan diizinkan memakai slot sama jika end <= start berikutnya.",
                "returns": "dict {slot_minimum, penugasan_per_id}",
            },
        ),
        edge_case_pool=(
            "daftar masukan kosong mengembalikan hasil netral tanpa error",
            "interval berdurasi nol (mulai == selesai) ditolak dengan ValueError",
            "interval negatif atau terbalik (mulai > selesai) memicu ValueError",
            "seluruh interval identik dan berbobot sama",
            "batas menyentuh tepat pada titik akhir [a, b) dan [b, c)",
            "nilai bobot nol atau pecahan float dengan presisi tetap",
        ),
    ),
    CodeTemplate(
        family="dependency_dag",
        variants=(
            {
                "lead": "Susun urutan eksekusi modul perangkat lunak berdasarkan graf ketergantungan berarah beserta deteksi siklus minimal.",
                "signature": "urutkan_modul_topologis(ketergantungan)",
                "core": "masukan berupa pemetaan {modul: iterable_prasyarat} di mana prasyarat harus dieksekusi sebelum modul.",
                "returns": "daftar nama modul terurut eksekusi",
            },
            {
                "lead": "Evaluasi jalur kritis proyek dari graf tugas berarah berbobot durasi dan tentukan tugas tanpa kelonggaran.",
                "signature": "hitung_jalur_kritis(daftar_tugas)",
                "core": "setiap tugas memiliki id, durasi non-negatif, dan daftar prasyarat; keluarkan panjang jalur terpanjang dan simpul kritis.",
                "returns": "dict {durasi_total, simpul_kritis, slack_per_tugas}",
            },
            {
                "lead": "Kompres komponen terhubung kuat pada graf layanan mikro menjadi DAG ringkas beserta pemetaan klaster tiap layanan.",
                "signature": "ringkas_komponen_layanan(graf_panggilan)",
                "core": "gunakan algoritma berbasis DFS deterministik tanpa rekursi berlebihan agar aman untuk rantai panjang.",
                "returns": "dict {komponen, sisi_dag}",
            },
        ),
        edge_case_pool=(
            "graf kosong tanpa simpul mengembalikan struktur kosong",
            "siklus dua simpul atau self-loop terdeteksi dan memicu ValueError dengan jejak simpul",
            "simpul terisolasi tanpa sisi masuk maupun sisi keluar tetap muncul",
            "prasyarat duplikat pada daftar ketergantungan dide-duplikasi",
            "rantai linear panjang 500 simpul tanpa RecursionError",
            "simpul yang direferensikan sebagai prasyarat tetapi tidak punya entri kunci eksplisit",
        ),
    ),
    CodeTemplate(
        family="bounded_graph_path",
        variants=(
            {
                "lead": "Cari rute pengiriman logistik termurah pada jaringan gudang berarah dengan batas jumlah transit maksimum.",
                "signature": "rute_termurah_terbatas(sisi_gudang, asal, tujuan, maks_transit)",
                "core": "setiap sisi berupa (dari, ke, biaya) non-negatif dan jumlah perpindahan sisi tidak boleh melampaui maks_transit + 1.",
                "returns": "tuple (total_biaya, daftar_simpul_rute) atau None bila tidak terjangkau",
            },
            {
                "lead": "Temukan seluruh simpul jaringan sensor yang dapat dijangkau dalam anggaran latensi tertentu dari gateway awal.",
                "signature": "jangkauan_sensor_terbatas(graf_latensi, sumber, batas_ms)",
                "core": "sisi tak berarah berbobot milidetik positif; catat jarak terpendek ke setiap simpul dalam batas anggaran.",
                "returns": "dict {simpul: latensi_terpendek} terurut menurut kunci simpul",
            },
            {
                "lead": "Tentukan jalur terpendek dengan penalti pergantian moda transportasi pada graf rute multi-moda.",
                "signature": "rute_multimoda(daftar_ruas, asal, tujuan, penalti_ganti)",
                "core": "setiap ruas berupa (simpul_a, simpul_b, moda, biaya); penalti ditambahkan setiap kali moda berubah di simpul transit.",
                "returns": "tuple (biaya_minimum, daftar_langkah)",
            },
        ),
        edge_case_pool=(
            "asal sama persis dengan tujuan menghasilkan biaya nol dan jalur beranggotakan satu simpul",
            "simpul tujuan tidak terjangkau atau tidak ada di graf",
            "bobot sisi negatif atau batas negatif memicu ValueError",
            "banyak sisi paralel antara sepasang simpul yang sama dengan biaya berbeda",
            "siklus nol-bobot atau graf terputus menjadi beberapa komponen",
            "batas_ms atau maks_transit bernilai nol",
        ),
    ),
    CodeTemplate(
        family="sliding_window_stream",
        variants=(
            {
                "lead": "Hitung nilai puncak berjalan pada jendela waktu bergeser berukuran K dari aliran metrik telemetri.",
                "signature": "maksimum_jendela_bergeser(nilai_deret, ukuran_k)",
                "core": "algoritma harus berjalan dalam kompleksitas O(n) menggunakan deque monotonik, bukan pemindaian ulang O(n*k).",
                "returns": "list nilai maksimum untuk setiap posisi jendela valid",
            },
            {
                "lead": "Cari sub-larik terpendek berjumlah minimal target S dari rangkaian pembacaan sensor bilangan bulat positif.",
                "signature": "sublarik_terpendek_target(angka, target_jumlah)",
                "core": "kembalikan panjang dan rentang indeks [mulai, akhir_eksklusif) sub-larik terpendek yang jumlahnya >= target_jumlah.",
                "returns": "tuple (panjang, mulai, akhir) atau None bila tidak ada",
            },
            {
                "lead": "Deteksi anomali lonjakan tingkat permintaan dalam jendela waktu stempel detik menggunakan pembatas laju geser.",
                "signature": "deteksi_lonjakan_permintaan(log_detik, jendela_detik, ambang)",
                "core": "masukan boleh belum terurut atau memuat stempel identik; hitung jumlah permintaan pada [t - jendela_detik + 1, t].",
                "returns": "list stempel waktu yang melampaui ambang secara terurut",
            },
        ),
        edge_case_pool=(
            "deret kosong atau lebih pendek dari ukuran jendela",
            "ukuran jendela == 1 dan ukuran jendela == len(deret)",
            "nilai elemen negatif, nol, maupun duplikat berurutan",
            "ukuran_k <= 0 atau target <= 0 ditolak dengan ValueError",
            "seluruh elemen identik di sepanjang deret",
            "stempel waktu tidak berurutan atau duplikat persis pada batas jendela",
        ),
    ),
    CodeTemplate(
        family="monotonic_search",
        variants=(
            {
                "lead": "Bagi paket berkas log ke dalam paling banyak M arsip berurutan agar ukuran arsip terbesar sekecil mungkin.",
                "signature": "partisi_kapasitas_minimum(ukuran_berkas, maks_arsip)",
                "core": "urutan berkas tidak boleh diacak; gunakan pencarian biner atas kapasitas maksimum dengan validasi serakah.",
                "returns": "tuple (kapasitas_minimum, daftar_partisi_sublist)",
            },
            {
                "lead": "Tentukan kecepatan pemrosesan minimum per jam agar seluruh batch pekerjaan selesai sebelum tenggat H jam.",
                "signature": "kecepatan_proses_minimum(beban_batch, batas_jam)",
                "core": "setiap batch hanya bisa diproses utuh per jam (pembulatan ke atas ceil(beban / laju)) secara berurutan.",
                "returns": "bilangan bulat laju minimum per jam",
            },
            {
                "lead": "Temukan jarak minimum maksimum untuk menempatkan K stasiun pengisian di sepanjang koridor posisi terurut.",
                "signature": "jarak_stasiun_optimal(posisi_kandidat, jumlah_stasiun)",
                "core": "posisi kandidat mungkin belum terurut dan dapat memuat duplikat yang harus ditolak atau dinormalisasi sesuai aturan.",
                "returns": "tuple (jarak_minimum_terbesar, daftar_posisi_terpilih)",
            },
        ),
        edge_case_pool=(
            "jumlah partisi atau stasiun melebihi kapasitas unik masukan memicu ValueError",
            "satu elemen saja atau seluruh elemen bernilai nol",
            "nilai kapasitas sangat besar hingga memicu risiko batas integer jika naif",
            "batas waktu tepat sama dengan jumlah elemen (satu item per jam)",
            "masukan memuat angka non-positif saat hanya bilangan bulat positif diizinkan",
            "posisi kandidat belum terurut dan memiliki selisih nol antar titik berdekatan",
        ),
    ),
    CodeTemplate(
        family="deterministic_cache",
        variants=(
            {
                "lead": "Implementasikan struktur cache LRU+TTL murni di memori dengan statistik hit, miss, dan eviksi deterministik.",
                "signature": "buat_cache_terbatas(kapasitas, ttl_detik)",
                "core": "kembalikan objek kelas dengan metode get(kunci, sekarang), put(kunci, nilai, sekarang), dan stats() tanpa thread/timer sistem.",
                "returns": "instance kelas cache dengan metode terdefinisi dan properti len()",
            },
            {
                "lead": "Rancang indeks kamus prefix (Trie) untuk pelengkapan otomatis kata berbahasa Indonesia berbobot frekuensi.",
                "signature": "buat_indeks_prefiks(daftar_kata_bobot)",
                "core": "mendukung pencarian top-K saran untuk awalan tertentu dengan normalisasi huruf kecil dan penyisipan inkremental.",
                "returns": "instance kelas indeks dengan metode saran(awalan, batas_k)",
            },
            {
                "lead": "Bangun penggabung snapshot konfigurasi bertingkat yang mencatat asal-usul layer setiap kunci terdalam.",
                "signature": "gabung_konfigurasi_berlapis(daftar_layer)",
                "core": "dict bersarang digabung secara mendalam (deep merge), sedangkan list dan skalar dari layer lebih akhir menimpa layer awal.",
                "returns": "tuple (konfigurasi_akhir, peta_asal_kunci)",
            },
        ),
        edge_case_pool=(
            "kapasitas <= 0 atau ttl_detik <= 0 ditolak dengan ValueError",
            "entri kedaluwarsa tepat pada batas waktu (sekarang - dibuat >= ttl) dianggap miss dan dibersihkan",
            "pembaruan nilai kunci yang sudah ada memperbarui urutan LRU tanpa memicu eviksi kunci lain",
            "awalan kosong atau tidak cocok dengan kata mana pun mengembalikan list kosong",
            "konflik tipe antara dict dan skalar pada jalur kunci yang sama di layer lebih baru",
            "kunci dengan titik atau karakter Unicode tidak boleh merusak struktur peta asal",
        ),
    ),
    CodeTemplate(
        family="structured_text_parser",
        variants=(
            {
                "lead": "Parse berkas CSV berkuotasi kustom secara manual tanpa modul `csv` menjadi daftar rekaman bertipe seragam.",
                "signature": "urai_csv_ketat(teks_csv, pemisah=',')",
                "core": "mendukung tanda kutip ganda ber-escape `\"\"`, jeda baris `\\n`/`\\r\\n` di dalam sel berkuotasi, serta validasi jumlah kolom per baris.",
                "returns": "tuple (daftar_header, daftar_dict_baris)",
            },
            {
                "lead": "Evaluasi ekspresi aritmetika bertanda kurung (+, -, *, /, //, %) dengan presedensi operator menggunakan shunting-yard.",
                "signature": "evaluasi_ekspresi_aman(ekspresi, variabel=None)",
                "core": "larang `eval`/`exec`/`ast.literal_eval`; dukung operator uner +/-, bilangan bulat/desimal, dan substitusi nama variabel.",
                "returns": "nilai float atau int hasil evaluasi akurat",
            },
            {
                "lead": "Normalisasi dan ringkas tabel transaksi teks berkolom lebar-tetap atau tab menjadi rekap agregat per kategori.",
                "signature": "agregasi_tabel_teks(teks_laporan)",
                "core": "abaikan baris komentar diawali `#` dan baris pemisah `---`; validasi format nominal ribuan/desimal secara deterministik.",
                "returns": "dict {kategori: {jumlah_baris, total_nilai}}",
            },
        ),
        edge_case_pool=(
            "kuotasi tidak tertutup sampai akhir berkas memicu ValueError dengan nomor baris",
            "jumlah sel baris berbeda dengan header memicu ValueError",
            "pembagian dengan nol atau tanda kurung tidak seimbang memicu ValueError",
            "masukan hanya berisi spasi atau komentar saja",
            "pemisah berturut-turut menghasilkan string kosong eksplisit, bukan diabaikan",
            "nama variabel tidak terdefinisi pada kamus variabel memicu ValueError",
        ),
    ),
    CodeTemplate(
        family="sequence_alignment_dp",
        variants=(
            {
                "lead": "Hitung jarak edit Damerau-Levenshtein terbatas beserta urutan operasi suntingan minimum antara dua string.",
                "signature": "jejak_suntingan_teks(sumber, sasaran)",
                "core": "operasi mencakup sisip, hapus, ganti, dan transposisi dua karakter bersebelahan masing-masing berbobot 1.",
                "returns": "tuple (jarak_minimum, daftar_operasi_terurut)",
            },
            {
                "lead": "Cocokkan daftar potongan kode atau token menjadi urutan diff baris minimal bergaya Myers/LCS deterministik.",
                "signature": "bandingkan_baris_minimal(baris_lama, baris_baru)",
                "core": "hasilkan daftar hunk berurutan bertanda `'='`, `'-'`, atau `'+'` dengan jumlah modifikasi seminimal mungkin.",
                "returns": "list tuple (tanda_op, isi_baris)",
            },
            {
                "lead": "Selesaikan masalah pengisian ransel pecahan dan diskret sekaligus dalam satu pemeriksa rasio nilai-bobot.",
                "signature": "optimasi_muatan_kapal(daftar_kargo, kapasitas_maks)",
                "core": "setiap kargo berupa (kode, bobot, nilai, dapat_dipecah); gunakan DP 0/1 untuk muatan utuh dan greedy sisa kapasitas jika diizinkan.",
                "returns": "dict {nilai_total, bobot_terpakai, rincian_kode}",
            },
        ),
        edge_case_pool=(
            "salah satu atau kedua masukan kosong",
            "kedua masukan identik menghasilkan nol perubahan",
            "karakter Unicode multi-byte atau spasi berulang tetap diperlakukan persis per karakter/baris",
            "bobot atau kapasitas bernilai nol atau negatif memicu ValueError",
            "beberapa jalur operasi optimal seri diselesaikan konsisten",
            "kapasitas lebih kecil dari semua muatan utuh yang tersedia",
        ),
    ),
)

TIE_BREAK_RULES: tuple[str, ...] = (
    "jika ada hasil seri, pilih kandidat dengan ID atau representasi leksikografis terkecil.",
    "jika ada hasil seri, pertahankan urutan kemunculan awal pada masukan (stabil).",
    "jika ada hasil seri, prioritaskan kandidat dengan jumlah langkah atau elemen lebih sedikit lalu leksikografis terkecil.",
)

FOCUS_PHRASES: tuple[str, ...] = (
    "audit integritas masukan nol-toleransi",
    "pemrosesan batch bervolume tinggi",
    "validasi skema ketat tanpa mutasi masukan",
    "penanganan ikatan seri secara deterministik",
    "eksekusi batas tepi skala ekstrem",
    "antrean sinkron dengan data terfragmentasi",
    "normalisasi rekaman duplikat dan kosong",
    "jaringan berkapasitas terbatas dan siklus",
    "deret waktu berstempel identik dan acak",
    "struktur terisolasi dan dependensi silang",
    "presisi numerik tanpa rekursi berlebih",
    "pemulihan aman saat masukan korup sebagian",
)


def _generate_candidate_pool(seed: int) -> list[dict[str, str]]:
    """Bangun pool deterministik seluruh kombinasi template x varian x kasus tepi."""
    rng = random.Random(seed)
    pool: list[dict[str, str]] = []
    for template in CODE_TEMPLATES:
        edges = template.edge_case_pool
        # Kombinasi pasangan dan trio indeks kasus tepi memberi ratusan variasi unik.
        combos: list[tuple[str, ...]] = []
        n_edges = len(edges)
        for i in range(n_edges):
            for j in range(i + 1, n_edges):
                combos.append((edges[i], edges[j]))
                for k in range(j + 1, n_edges):
                    combos.append((edges[i], edges[j], edges[k]))
        for variant_idx, variant in enumerate(template.variants):
            for combo_idx, edge_combo in enumerate(combos):
                tie_rule = TIE_BREAK_RULES[(combo_idx + len(variant["signature"])) % len(TIE_BREAK_RULES)]
                focus_phrase = FOCUS_PHRASES[(combo_idx + variant_idx) % len(FOCUS_PHRASES)]
                instruction = template.render_instruction(variant, focus_phrase, edge_combo, tie_rule)
                pool.append(
                    {
                        "family": template.family,
                        "signature": variant["signature"],
                        "instruction": instruction,
                    }
                )
    rng.shuffle(pool)
    return pool


def generate_code_episodes(
    *,
    count: int,
    prefix: str = DEFAULT_PREFIX,
    seed: int = 20261117,
    frozen_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Hasilkan `count` episode corpus `code` tervalidasi penuh oleh `corpus_lint`."""
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise CorpusFactoryCodeError("Parameter `--count` wajib bilangan bulat positif (> 0).")
    if not isinstance(prefix, str) or not prefix.strip():
        raise CorpusFactoryCodeError("Parameter `--prefix` wajib berupa string tidak kosong.")
    if any(ch.isspace() for ch in prefix):
        raise CorpusFactoryCodeError("Parameter `--prefix` tidak boleh mengandung spasi.")

    frozen_prefixes: dict[str, dict[str, Any]] = {}
    if frozen_paths:
        try:
            frozen_prefixes = load_frozen_prefixes(frozen_paths)
        except InvalidInputError as exc:
            raise CorpusFactoryCodeError(str(exc)) from exc

    pool = _generate_candidate_pool(seed)
    selected: list[dict[str, Any]] = []
    seen_prefix60: set[str] = set(frozen_prefixes.keys())
    skipped_frozen_collisions = 0
    skipped_duplicate_prefix60 = 0
    family_counts: dict[str, int] = {}

    width = max(3, len(str(count)))
    for candidate in pool:
        if len(selected) >= count:
            break
        instr = candidate["instruction"]
        prefix60 = instr[:FROZEN_PREFIX_LEN]
        if prefix60 in frozen_prefixes:
            skipped_frozen_collisions += 1
            continue
        if prefix60 in seen_prefix60:
            skipped_duplicate_prefix60 += 1
            continue
        seen_prefix60.add(prefix60)
        seq = len(selected) + 1
        episode_id = f"{prefix}{seq:0{width}d}"
        selected.append(
            {
                "id": episode_id,
                "kind": "episode",
                "task_kind": "code",
                "instruction": instr,
                "_family": candidate["family"],
            }
        )
        family_counts[candidate["family"]] = family_counts.get(candidate["family"], 0) + 1

    if len(selected) < count:
        raise CorpusFactoryCodeError(
            f"Kandidat unik tidak mencukupi: diminta {count}, tersedia {len(selected)} "
            f"(tabrakan frozen={skipped_frozen_collisions}, duplikat prefix60={skipped_duplicate_prefix60})."
        )

    lines = [
        json.dumps(
            {
                "id": row["id"],
                "kind": row["kind"],
                "task_kind": row["task_kind"],
                "instruction": row["instruction"],
            },
            ensure_ascii=False,
        )
        for row in selected
    ]

    lint_report = lint_lines(
        lines,
        corpus_name="<generated:corpus_factory_code>",
        prefixes=[prefix],
        frozen_prefixes=frozen_prefixes,
    )
    if not lint_report["valid"]:
        raise CorpusFactoryCodeError(
            f"Validasi internal `corpus_lint` gagal: {lint_report['violations'][:3]}"
        )

    return {
        "schema": FACTORY_SCHEMA,
        "count": len(lines),
        "prefix": prefix,
        "seed": seed,
        "family_counts": dict(sorted(family_counts.items())),
        "skipped_frozen_collisions": skipped_frozen_collisions,
        "skipped_duplicate_prefix60": skipped_duplicate_prefix60,
        "lint_ok": lint_report["valid"],
        "lint_summary": lint_report["summary"],
        "lines": lines,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _parse_frozen_args(values: list[str] | None) -> list[Path]:
    if not values:
        return []
    paths: list[Path] = []
    for raw in values:
        for item in raw.split(","):
            cleaned = item.strip()
            if not cleaned:
                raise CorpusFactoryCodeError("Nilai argumen `--frozen` tidak boleh kosong.")
            paths.append(Path(cleaned))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generator corpus episode `code` terparameter dengan swa-validasi corpus_lint."
    )
    parser.add_argument("--count", type=int, required=True, help="Jumlah episode yang dihasilkan (> 0).")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"Prefix ID episode (default: {DEFAULT_PREFIX}).")
    parser.add_argument("--seed", type=int, default=20261117, help="Seed PRNG deterministik.")
    parser.add_argument(
        "--frozen",
        action="append",
        help="Path corpus beku JSONL untuk menolak tabrakan prefix 60 karakter (bisa berulang/dipisah koma).",
    )
    parser.add_argument("--out", required=True, help="Path berkas keluaran JSONL.")
    parser.add_argument("--summary-out", help="Path opsional ringkasan JSON generasi dan hasil lint.")
    args = parser.parse_args(argv)

    try:
        frozen_paths = _parse_frozen_args(args.frozen)
        result = generate_code_episodes(
            count=args.count,
            prefix=args.prefix,
            seed=args.seed,
            frozen_paths=frozen_paths,
        )
    except CorpusFactoryCodeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    _atomic_write_text(out_path, "\n".join(result["lines"]) + "\n")

    summary_payload = {k: v for k, v in result.items() if k != "lines"}
    summary_payload["out"] = str(out_path)
    if args.summary_out:
        _atomic_write_text(
            Path(args.summary_out),
            json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n",
        )
    print(json.dumps(summary_payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
