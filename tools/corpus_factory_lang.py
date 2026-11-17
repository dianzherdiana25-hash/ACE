#!/usr/bin/env python3
"""Generator parameterized soal corpus `language` berkendala tumpuk ACE (WS-B #5).

Menghasilkan:
1. Berkas kandidat corpus JSONL (`{id, kind, task_kind, instruction}`) yang lolos `corpus_lint`.
2. Spesifikasi kendala mekanis pendamping per episode (`<spec_dir>/<id>.spec.json`)
   mencakup jumlah kata tepat, jumlah kalimat tepat, 2 frasa verbatim wajib,
   daftar kata/akar kata terlarang beserta imbuhan Indonesia, serta urutan fakta wajib.
3. Jawaban sampel terverifikasi (`<sample_dir>/<id>.txt`) yang dipastikan lulus
   100% pemeriksaan deterministik `verify_constraint_spec`.

Catatan ketergantungan: mengimpor `tools.corpus_lint` (PR #256).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import re
import sys
from typing import Any

from tools.corpus_lint import (
    FROZEN_PREFIX_LEN,
    InvalidInputError,
    lint_lines,
    load_frozen_prefixes,
)

FACTORY_LANG_SCHEMA = "ace.corpus-factory-lang.v1"
CONSTRAINT_SPEC_SCHEMA = "ace.lang-constraint-spec.v1"
DEFAULT_PREFIX = "lang_gen_"

_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")

_PREFIX_VARIANTS = (
    "",
    "me",
    "mem",
    "men",
    "meng",
    "meny",
    "di",
    "ber",
    "be",
    "ter",
    "te",
    "pe",
    "pem",
    "pen",
    "peng",
    "peny",
    "per",
    "ke",
    "se",
    "memper",
    "diper",
    "keber",
    "keter",
)
_SUFFIX_VARIANTS = (
    "",
    "kan",
    "an",
    "i",
    "nya",
    "lah",
    "kah",
    "kannya",
    "inya",
    "annya",
)


class CorpusFactoryLangError(ValueError):
    """Kesalahan parameter masukan atau kegagalan verifikasi kendala episode bahasa."""


def tokenize_words(text: str) -> list[str]:
    """Pecah teks menjadi token kata secara deterministik."""
    return _WORD_RE.findall(text)


def split_sentences(text: str) -> list[str]:
    """Pecah teks menjadi kalimat tidak kosong berbasis tanda akhir `.`, `!`, `?`."""
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]
    return parts


def _expand_indonesian_affix_forms(root: str) -> set[str]:
    """Bangun himpunan kata terlarang untuk akar kata beserta variasi imbuhan Indonesia."""
    clean = root.strip().lower()
    if not clean:
        return set()
    stems = {clean}
    # Peluluhan konsonan awal K/P/T/S pada awalan meN-/peN-.
    if len(clean) > 2 and clean[0] in {"k", "p", "t", "s"}:
        stems.add(clean[1:])
    forms: set[str] = set()
    for pref in _PREFIX_VARIANTS:
        for stem in stems:
            # Hindari peluluhan tanpa awalan nasal.
            if stem != clean and not any(pref.endswith(p) for p in ("me", "mem", "men", "meng", "meny", "pe", "pem", "pen", "peng", "peny")):
                continue
            for suff in _SUFFIX_VARIANTS:
                forms.add(f"{pref}{stem}{suff}")
    return forms


def verify_constraint_spec(text: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Pemeriksa kendala mekanis deterministik terhadap spesifikasi episode bahasa."""
    if not isinstance(text, str) or not text.strip():
        raise CorpusFactoryLangError("Teks jawaban untuk verifikasi wajib string tidak kosong.")

    words = tokenize_words(text)
    sentences = split_sentences(text)
    lowered_words = [w.lower() for w in words]

    checks: dict[str, Any] = {}
    all_passed = True

    wc_spec = spec.get("word_count", {})
    exact_words = wc_spec.get("exact")
    wc_passed = len(words) == exact_words
    checks["word_count"] = {
        "passed": wc_passed,
        "expected": exact_words,
        "actual": len(words),
    }
    all_passed = all_passed and wc_passed

    sc_spec = spec.get("sentence_count", {})
    exact_sentences = sc_spec.get("exact")
    sc_passed = len(sentences) == exact_sentences
    checks["sentence_count"] = {
        "passed": sc_passed,
        "expected": exact_sentences,
        "actual": len(sentences),
    }
    all_passed = all_passed and sc_passed

    req_phrases = list(spec.get("required_phrases", []))
    missing_phrases = [p for p in req_phrases if p not in text]
    phrases_passed = len(missing_phrases) == 0 and len(req_phrases) >= 2
    checks["required_phrases"] = {
        "passed": phrases_passed,
        "expected": req_phrases,
        "missing": missing_phrases,
    }
    all_passed = all_passed and phrases_passed

    forbidden_roots = list(spec.get("forbidden_affix_roots", []))
    forbidden_exact = {w.lower() for w in spec.get("forbidden_words", [])}
    expanded_forbidden = set(forbidden_exact)
    root_map: dict[str, str] = {w: w for w in forbidden_exact}
    for root in forbidden_roots:
        for form in _expand_indonesian_affix_forms(root):
            expanded_forbidden.add(form)
            root_map.setdefault(form, root)

    forbidden_hits: list[dict[str, str]] = []
    for idx, token in enumerate(lowered_words):
        if token in expanded_forbidden:
            forbidden_hits.append(
                {
                    "token": words[idx],
                    "matched_root": root_map.get(token, token),
                }
            )
    forb_passed = len(forbidden_hits) == 0
    checks["forbidden_words"] = {
        "passed": forb_passed,
        "roots": forbidden_roots,
        "hits": forbidden_hits,
    }
    all_passed = all_passed and forb_passed

    req_order = list(spec.get("required_order", []))
    order_positions: list[dict[str, Any]] = []
    order_passed = len(req_order) >= 2
    last_pos = -1
    for fact in req_order:
        pos = text.find(fact)
        order_positions.append({"fact": fact, "index": pos})
        if pos < 0 or pos <= last_pos:
            order_passed = False
        if pos >= 0:
            last_pos = pos
    checks["required_order"] = {
        "passed": order_passed,
        "sequence": order_positions,
    }
    all_passed = all_passed and order_passed

    return {
        "schema": CONSTRAINT_SPEC_SCHEMA,
        "episode_id": spec.get("episode_id", ""),
        "passed": all_passed,
        "checks": checks,
    }


@dataclass(frozen=True)
class LangScenario:
    """Skenario bahasa Indonesia berkendala tumpuk dengan penyusun jawaban terkalibrasi."""

    domain: str
    opening_prefix: str
    topic_prompt: str
    phrases: tuple[str, str]
    forbidden_roots: tuple[str, str, str]
    ordered_facts: tuple[str, str]
    sentence_modes: tuple[tuple[str, ...], ...]


LANG_SCENARIOS: tuple[LangScenario, ...] = (
    LangScenario(
        domain="audit_log_pembangkit",
        opening_prefix="Ringkasan insiden jaringan gardu",
        topic_prompt="jelaskan penanganan gangguan daya gardu induk secara ringkas bagi tim siaga malam.",
        phrases=("jalur cadangan aktif", "ambang suhu aman"),
        forbidden_roots=("rusak", "padam", "matikan"),
        ordered_facts=("lonjakan beban pukul 21:05", "laporan kalibrasi tuntas"),
        sentence_modes=(
            (
                "Catatan lapangan mencatat lonjakan beban pukul 21:05 pada penyulang timur setelah hujan deras mengguyur kawasan industri.",
                "Operator segera memindahkan aliran menuju jalur cadangan aktif agar layanan rumah sakit tetap stabil sepanjang malam.",
                "Sensor panel menunjukkan suhu inti turun ke ambang suhu aman sehingga laporan kalibrasi tuntas dikirim ke pusat kendali.",
            ),
            (
                "Catatan lapangan mengonfirmasi lonjakan beban pukul 21:05 di gardu sektor timur ketika beban pabrik memuncak bersamaan.",
                "Regu jaga langsung mengaktifkan jalur cadangan aktif tanpa jeda pasokan bagi pelanggan prioritas kota.",
                "Pendinginan bekerja normal dan panel mencapai ambang suhu aman tepat sebelum subuh tiba.",
                "Setelah verifikasi ulang tekanan trafo, laporan kalibrasi tuntas diarsipkan ke buku log resmi malam itu.",
            ),
        ),
    ),
    LangScenario(
        domain="preservasi_arsip_museum",
        opening_prefix="Protokol ruang simpan naskah kuno",
        topic_prompt="paparkan tata cara pemindahan koleksi kertas abad ke-19 ke lemari bebas asam.",
        phrases=("kelembapan ruang terjaga", "sarung tangan nitril"),
        forbidden_roots=("sentuh", "robek", "lembab"),
        ordered_facts=("pemetaan indeks awal", "segel peti dibuka"),
        sentence_modes=(
            (
                "Petugas kuratorial menyelesaikan pemetaan indeks awal seluruh bundel surat niaga sebelum rak lama dikosongkan.",
                "Setiap berkas diangkat memakai sarung tangan nitril dan alas penyangga karton bebas lignin agar serat kertas tetap utuh.",
                "Setelah segel peti dibuka di ruang karantina, sistem pengatur memastikan kelembapan ruang terjaga pada lima puluh persen.",
            ),
            (
                "Tim konservasi menjalankan pemetaan indeks awal beserta pemotretan resolusi tinggi atas tiap halaman rapuh.",
                "Semua pengelola arsip wajib mengenakan sarung tangan nitril selama memindahkan map menuju baki penyimpanan baru.",
                "Ketika segel peti dibuka untuk inspeksi akhir, alat pantau membuktikan kelembapan ruang terjaga stabil sepanjang pekan.",
                "Lemari baja berventilasi saring karbon kemudian dikunci kembali sesuai prosedur baku.",
            ),
        ),
    ),
    LangScenario(
        domain="koordinasi_dermaga_dingin",
        opening_prefix="Catatan muat komoditas rantai dingin",
        topic_prompt="uraikan alur pemuatan hasil tangkapan laut ke kontainer pendingin pelabuhan.",
        phrases=("segel termal rapat", "antrean bongkar lancar"),
        forbidden_roots=("busuk", "bocor", "tunda"),
        ordered_facts=("pemeriksaan suhu palka", "kapal berlayar tepat"),
        sentence_modes=(
            (
                "Inspektur pelabuhan memulai pemeriksaan suhu palka begitu perahu nelayan bersandar di dermaga utara pukul empat pagi.",
                "Pekerja memindahkan peti ikan menuju truk berpendingin dengan cepat agar antrean bongkar lancar tanpa penumpukan di teras dermaga.",
                "Petugas memastikan segel termal rapat pada pintu kontainer sebelum kapal berlayar tepat menuju gudang tujuan.",
            ),
            (
                "Tim mutu melakukan pemeriksaan suhu palka untuk menjamin kesegaran muatan sebelum diturunkan ke peti berinsulasi.",
                "Koordinator lapangan menata jalur angkut secara paralel sehingga antrean bongkar lancar meski tiga perahu tiba berurutan.",
                "Sensor pintu menunjukkan segel termal rapat dan suhu kabin bertahan pada minus delapan belas derajat.",
                "Seluruh dokumen manifes disahkan oleh syahbandar sehingga kapal berlayar tepat mengikuti jadwal pasang surut.",
            ),
        ),
    ),
    LangScenario(
        domain="kalibrasi_instrumen_lab",
        opening_prefix="Prosedur uji timbangan analitik mikro",
        topic_prompt="tuliskan langkah penyetelan ulang timbangan presisi sebelum pengukuran sampel air.",
        phrases=("gelembung nivo tengah", "bobot standar tersertifikasi"),
        forbidden_roots=("goyang", "geser", "keliru"),
        ordered_facts=("meja granit dibersihkan", "pengukuran perdana dicatat"),
        sentence_modes=(
            (
                "Teknisi memastikan meja granit dibersihkan dari debu halus sebelum penutup kaca timbangan dibuka kembali.",
                "Kaki penyangga diputar perlahan sampai gelembung nivo tengah berada persis di dalam lingkaran acuan.",
                "Kalibrasi internal dijalankan memakai bobot standar tersertifikasi lalu pengukuran perdana dicatat pada lembar kendali mutu.",
            ),
            (
                "Sebelum menyalakan unit optik, meja granit dibersihkan dengan cairan bebas residu dan kain serat mikro.",
                "Posisi alas diseimbangkan dengan teliti hingga gelembung nivo tengah diam sempurna di titik nol mekanis.",
                "Penguji meletakkan bobot standar tersertifikasi seberat seratus gram untuk memverifikasi kelurusan skala digital.",
                "Setelah angka pembacaan stabil selama lima detik, pengukuran perdana dicatat menuju basis data laboratorium.",
            ),
        ),
    ),
    LangScenario(
        domain="manajemen_air_irigasi",
        opening_prefix="Laporan pengaturan pintu air tersier",
        topic_prompt="sampaikan jadwal pembagian debit saluran irigasi desa selama musim kemarau awal.",
        phrases=("debit tersier merata", "pintu utama terkunci"),
        forbidden_roots=("banjir", "kering", "tutup"),
        ordered_facts=("ketinggian waduk diukur", "giliran blok timur"),
        sentence_modes=(
            (
                "Penjaga bendung memastikan ketinggian waduk diukur sejak pukul lima pagi sebelum jadwal pembukaan katup diumumkan.",
                "Pengaturan bukaan katup bertahap menjaga debit tersier merata untuk tiga kelompok tani sepanjang saluran selatan.",
                "Pada sore hari pintu utama terkunci rapat setelah giliran blok timur menerima jatah pengairan penuh.",
            ),
            (
                "Setiap fajar ketinggian waduk diukur secara manual pada papan skala guna mencocokkan data telemetri harian.",
                "Petugas mengatur papan sekat bertingkat agar debit tersier merata sampai ke petak sawah terjauh di hilir.",
                "Setelah masa alir berakhir, pintu utama terkunci memakai gembok bernomor seri sesuai kesepakatan warga.",
                "Saluran kemudian dialihkan menuju giliran blok timur yang sudah menyiapkan lahan tanam serempak.",
            ),
        ),
    ),
    LangScenario(
        domain="jalur_kereta_komuter",
        opening_prefix="Berita pengendalian lintas rel komuter",
        topic_prompt="susun laporan pemulihan jadwal perjalanan kereta setelah penggantian wesel malam.",
        phrases=("lintas utara lancar", "sinyal masuk hijau"),
        forbidden_roots=("tabrak", "telat", "macet"),
        ordered_facts=("inspeksi baut rel", "rangkaian perdana melintas"),
        sentence_modes=(
            (
                "Regu prasarana menuntaskan inspeksi baut rel di percabangan stasiun pusat dua puluh menit sebelum fajar.",
                "Petugas menara melihat sinyal masuk hijau menyala stabil di seluruh petak jalur uji.",
                "Setelah rangkaian perdana melintas dengan kecepatan terukur, lintas utara lancar melayani penumpang pagi tepat waktu.",
            ),
            (
                "Tim lintasan melaksanakan inspeksi baut rel serta mengukur lebar sepur di titik wesel baru menggunakan alat ukur optik.",
                "Pusat kendali memverifikasi sinyal masuk hijau beserta indikator posisi lidah wesel di layar pemantau.",
                "Masinis uji membawa rangkaian perdana melintas tanpa getaran berlebih melewati seluruh sambungan rel.",
                "Mulai pukul lima lewat lima belas menit, lintas utara lancar beroperasi sesuai grafik perjalanan resmi.",
            ),
        ),
    ),
    LangScenario(
        domain="restorasi_hutan_bakau",
        opening_prefix="Catatan pemantauan zona pesisir timur",
        topic_prompt="laporkan kemajuan penanaman bibit bakau dan pengukuran salinitas tambak penyangga.",
        phrases=("akar muda kokoh", "pasang surut terpantau"),
        forbidden_roots=("tebang", "mati", "rusak"),
        ordered_facts=("pemasangan ajir bambu", "salinitas tambak stabil"),
        sentence_modes=(
            (
                "Relawan desa memulai pemasangan ajir bambu di sepanjang tepian lumpur guna menahan bibit muda dari arus ombak.",
                "Pengamatan pekan keempat memperlihatkan akar muda kokoh menancap dalam sementara pasang surut terpantau lewat patok ukur.",
                "Data lapangan juga membuktikan salinitas tambak stabil di kisaran dua puluh empat permil.",
            ),
            (
                "Kelompok tani pesisir merampungkan pemasangan ajir bambu pada tiga hektare lahan terbuka di sisi muara.",
                "Berbagai jenis bibit bertahan baik karena akar muda kokoh mencengkeram sedimen halus sejak bulan pertama.",
                "Pencatatan harian memastikan pasang surut terpantau secara konsisten untuk menjaga sirkulasi air tambak rakyat.",
                "Hasil uji air akhir bulan menunjukkan salinitas tambak stabil mendukung kehidupan kepiting bakau.",
            ),
        ),
    ),
    LangScenario(
        domain="pengiriman_obat_klinik",
        opening_prefix="Laporan distribusi vaksin klinik terpencil",
        topic_prompt="jelaskan pengiriman kotak pendingin vaksin dari gudang kabupaten ke puskesmas pegunungan.",
        phrases=("suhu kotak terjaga", "segel kurir utuh"),
        forbidden_roots=("pecah", "hilang", "batal"),
        ordered_facts=("pengecekan gel dingin", "berita acara ditandatangani"),
        sentence_modes=(
            (
                "Apoteker gudang melakukan pengecekan gel dingin sebelum memasukkan botol vaksin ke dalam kotak insulasi portabel.",
                "Setiba di klinik lereng gunung, petugas memastikan suhu kotak terjaga pada empat derajat serta segel kurir utuh.",
                "Seluruh isi dihitung ulang lalu berita acara ditandatangani oleh kepala gudang dan bidan desa.",
            ),
            (
                "Persiapan keberangkatan diawali pengecekan gel dingin dan penataan sensor pencatat suhu di bagian tengah kemasan.",
                "Sepanjang perjalanan darat tiga jam melalui jalan menanjak, suhu kotak terjaga dalam rentang dua hingga delapan derajat.",
                "Petugas penerima memeriksa nomor seri pengaman dan mengonfirmasi segel kurir utuh tanpa bekas tekanan.",
                "Sesudah catatan grafik termometer dicetak rangkap dua, berita acara ditandatangani di ruang imunisasi.",
            ),
        ),
    ),
)

DOMAIN_CONTEXT_TAGS: tuple[str, ...] = (
    "edisi shift pagi",
    "edisi shift siang",
    "edisi audit mingguan",
    "edisi verifikasi triwulan",
    "edisi siaga cuaca",
    "edisi evaluasi internal",
    "edisi pemantauan berkala",
    "edisi catatan operasi",
)


def _generate_pool(seed: int) -> list[dict[str, Any]]:
    """Bangun pool kombinasi terverifikasi skenario x konteks x mode jawaban."""
    rng = random.Random(seed)
    pool: list[dict[str, Any]] = []
    for scenario in LANG_SCENARIOS:
        for mode_idx, sentences in enumerate(scenario.sentence_modes):
            sample_text = " ".join(sentences)
            sample_words = tokenize_words(sample_text)
            sample_sentences = split_sentences(sample_text)
            for tag_idx, ctx_tag in enumerate(DOMAIN_CONTEXT_TAGS):
                # Variasikan jumlah/urutan kata terlarang untuk kombinasi unik.
                rot = (mode_idx + tag_idx) % len(scenario.forbidden_roots)
                forb = tuple(
                    scenario.forbidden_roots[(i + rot) % len(scenario.forbidden_roots)]
                    for i in range(len(scenario.forbidden_roots))
                )
                exact_w = len(sample_words)
                exact_s = len(sample_sentences)
                p1, p2 = scenario.phrases
                f_a, f_b = scenario.ordered_facts
                forb_str = ", ".join(f"`{r}` (termasuk bentuk berimbuhan)" for r in forb)

                instruction = (
                    f"{scenario.opening_prefix} [{exact_w}k/{exact_s}kal, {ctx_tag}]: "
                    f"{scenario.topic_prompt} "
                    f"Jawab dalam TEPAT {exact_w} kata dan TEPAT {exact_s} kalimat Bahasa Indonesia baku. "
                    f"Wajib memuat persis dua frasa berikut: \"{p1}\" dan \"{p2}\". "
                    f"Dilarang keras memakai kata atau turunan dari: {forb_str}. "
                    f"Fakta \"{f_a}\" wajib muncul lebih dahulu daripada fakta \"{f_b}\"."
                )
                pool.append(
                    {
                        "domain": scenario.domain,
                        "instruction": instruction,
                        "sample_answer": sample_text,
                        "word_count": exact_w,
                        "sentence_count": exact_s,
                        "phrases": [p1, p2],
                        "forbidden_roots": list(forb),
                        "ordered_facts": [f_a, f_b],
                    }
                )
    rng.shuffle(pool)
    return pool


def generate_lang_episodes(
    *,
    count: int,
    prefix: str = DEFAULT_PREFIX,
    seed: int = 20261117,
    frozen_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Hasilkan `count` episode bahasa berkendala tumpuk + spec + sampel terverifikasi."""
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise CorpusFactoryLangError("Parameter `--count` wajib bilangan bulat positif (> 0).")
    if not isinstance(prefix, str) or not prefix.strip():
        raise CorpusFactoryLangError("Parameter `--prefix` wajib berupa string tidak kosong.")
    if any(ch.isspace() for ch in prefix):
        raise CorpusFactoryLangError("Parameter `--prefix` tidak boleh mengandung spasi.")

    frozen_prefixes: dict[str, dict[str, Any]] = {}
    if frozen_paths:
        try:
            frozen_prefixes = load_frozen_prefixes(frozen_paths)
        except InvalidInputError as exc:
            raise CorpusFactoryLangError(str(exc)) from exc

    pool = _generate_pool(seed)
    seen_prefix60: set[str] = set(frozen_prefixes.keys())
    skipped_frozen = 0
    skipped_dup60 = 0
    episodes: list[dict[str, Any]] = []
    specs: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    lines: list[str] = []
    width = max(3, len(str(count)))

    for cand in pool:
        if len(episodes) >= count:
            break
        instr = cand["instruction"]
        p60 = instr[:FROZEN_PREFIX_LEN]
        if p60 in frozen_prefixes:
            skipped_frozen += 1
            continue
        if p60 in seen_prefix60:
            skipped_dup60 += 1
            continue

        seq = len(episodes) + 1
        ep_id = f"{prefix}{seq:0{width}d}"
        spec = {
            "schema": CONSTRAINT_SPEC_SCHEMA,
            "episode_id": ep_id,
            "domain": cand["domain"],
            "word_count": {"exact": cand["word_count"]},
            "sentence_count": {"exact": cand["sentence_count"]},
            "required_phrases": cand["phrases"],
            "forbidden_words": [],
            "forbidden_affix_roots": cand["forbidden_roots"],
            "required_order": cand["ordered_facts"],
        }
        check = verify_constraint_spec(cand["sample_answer"], spec)
        if not check["passed"]:
            raise CorpusFactoryLangError(
                f"Sampel internal gagal verifikasi kendala untuk domain '{cand['domain']}': {check['checks']}"
            )

        seen_prefix60.add(p60)
        ep_obj = {
            "id": ep_id,
            "kind": "episode",
            "task_kind": "language",
            "instruction": instr,
        }
        episodes.append(ep_obj)
        specs.append(spec)
        samples.append(
            {
                "episode_id": ep_id,
                "answer_text": cand["sample_answer"],
                "verification": check,
            }
        )
        lines.append(json.dumps(ep_obj, ensure_ascii=False))

    if len(episodes) < count:
        raise CorpusFactoryLangError(
            f"Kandidat episode bahasa unik tidak mencukupi: diminta {count}, tersedia {len(episodes)} "
            f"(tabrakan frozen={skipped_frozen}, duplikat prefix60={skipped_dup60})."
        )

    lint_report = lint_lines(
        lines,
        corpus_name="<generated:corpus_factory_lang>",
        prefixes=[prefix],
        frozen_prefixes=frozen_prefixes,
    )
    if not lint_report["valid"]:
        raise CorpusFactoryLangError(
            f"Validasi internal `corpus_lint` gagal: {lint_report['violations'][:3]}"
        )

    return {
        "schema": FACTORY_LANG_SCHEMA,
        "count": len(episodes),
        "prefix": prefix,
        "seed": seed,
        "all_samples_verified": all(s["verification"]["passed"] for s in samples),
        "skipped_frozen_collisions": skipped_frozen,
        "skipped_duplicate_prefix60": skipped_dup60,
        "lint_ok": lint_report["valid"],
        "lines": lines,
        "specs": specs,
        "samples": samples,
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
                raise CorpusFactoryLangError("Nilai argumen `--frozen` tidak boleh kosong.")
            paths.append(Path(cleaned))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generator corpus episode `language` berkendala tumpuk + spec JSON + jawaban sampel terverifikasi."
    )
    parser.add_argument("--count", type=int, required=True, help="Jumlah episode yang dihasilkan (> 0).")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"Prefix ID episode (default: {DEFAULT_PREFIX}).")
    parser.add_argument("--seed", type=int, default=20261117, help="Seed PRNG deterministik.")
    parser.add_argument(
        "--frozen",
        action="append",
        help="Path corpus beku JSONL untuk menolak tabrakan prefix 60 karakter.",
    )
    parser.add_argument("--out", required=True, help="Path berkas keluaran JSONL corpus.")
    parser.add_argument("--spec-dir", required=True, help="Direktori keluaran berkas `<id>.spec.json`.")
    parser.add_argument("--sample-dir", help="Direktori opsional keluaran jawaban sampel terverifikasi `<id>.txt`.")
    parser.add_argument("--summary-out", help="Path opsional ringkasan JSON.")
    args = parser.parse_args(argv)

    try:
        frozen_paths = _parse_frozen_args(args.frozen)
        result = generate_lang_episodes(
            count=args.count,
            prefix=args.prefix,
            seed=args.seed,
            frozen_paths=frozen_paths,
        )
    except CorpusFactoryLangError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    _atomic_write_text(out_path, "\n".join(result["lines"]) + "\n")

    spec_dir = Path(args.spec_dir)
    for spec in result["specs"]:
        _atomic_write_text(
            spec_dir / f"{spec['episode_id']}.spec.json",
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        )

    if args.sample_dir:
        sample_dir = Path(args.sample_dir)
        for sample in result["samples"]:
            _atomic_write_text(
                sample_dir / f"{sample['episode_id']}.txt",
                sample["answer_text"] + "\n",
            )

    summary = {
        "schema": result["schema"],
        "count": result["count"],
        "prefix": result["prefix"],
        "seed": result["seed"],
        "all_samples_verified": result["all_samples_verified"],
        "skipped_frozen_collisions": result["skipped_frozen_collisions"],
        "skipped_duplicate_prefix60": result["skipped_duplicate_prefix60"],
        "lint_ok": result["lint_ok"],
        "out": str(out_path),
        "spec_dir": str(spec_dir),
    }
    if args.sample_dir:
        summary["sample_dir"] = str(args.sample_dir)
    if args.summary_out:
        _atomic_write_text(Path(args.summary_out), json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
