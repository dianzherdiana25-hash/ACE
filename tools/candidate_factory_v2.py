#!/usr/bin/env python3
"""Pabrik kandidat corpus v2 (Garis B1).

Memperluas generasi kandidat kode & bahasa ACE secara berdiri sendiri tanpa
mengubah generator/corpus beku lama, dengan fitur:
1. Kendala bertingkat yang dapat diatur jumlahnya (`--constraints-per-episode`, 2..6).
2. Gelombang Bahasa Indonesia baru (`grav_lang_id_*`) dan gelombang multibahasa
   (`grav_lang_ml_*`) yang wajib mencakup minimal 4 bahasa (`id`, `en`, `es`,
   `de`, `fr`).
3. Kandidat kode berkendala komposit (`grav_code_v2_*`): algoritma spesifik +
   batas kompleksitas waktu/ruang + larangan alat/impor + format persis.
4. Validasi internal wajib (fail-closed): kandidat yang gagal pemeriksaan
   mekanis, skema, duplikat, atau lint tidak pernah ditulis ke keluaran.
5. Sensus kesiapan per gelombang (`readiness_census.json`).

Catatan: hanya menghasilkan berkas kandidat di direktori keluaran target;
bukan instrumen judge/scorer dan tidak menulis ke direktori/korpus beku.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
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

FACTORY_V2_SCHEMA = "ace.candidate-factory-v2.v1"
LANG_SPEC_V2_SCHEMA = "ace.lang-layered-spec.v2"
CODE_SPEC_V2_SCHEMA = "ace.code-composite-spec.v2"
CENSUS_V2_SCHEMA = "ace.candidate-readiness-census.v2"

DEFAULT_ID_PREFIX = "grav_lang_id_"
DEFAULT_ML_PREFIX = "grav_lang_ml_"
DEFAULT_CODE_PREFIX = "grav_code_v2_"

MIN_CONSTRAINTS_PER_EPISODE = 2
MAX_CONSTRAINTS_PER_EPISODE = 6
MIN_MULTILINGUAL_LANGUAGES = 4

CONSTRAINT_LAYERS: tuple[str, ...] = (
    "word_count",
    "sentence_count",
    "required_phrases",
    "forbidden_words",
    "required_order",
    "surface_hygiene",
)

SUPPORTED_MULTILINGUAL_LANGUAGES: tuple[str, ...] = ("id", "en", "es", "de", "fr")

_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")

_ID_PREFIX_VARIANTS = (
    "", "me", "mem", "men", "meng", "meny", "di", "ber", "be",
    "ter", "te", "pe", "pem", "pen", "peng", "peny", "per",
    "ke", "se", "memper", "diper", "keber", "keter",
)
_ID_SUFFIX_VARIANTS = ("", "kan", "an", "i", "nya", "lah", "kah", "kannya", "inya", "annya")
_MULTILINGUAL_INFLECTIONS: dict[str, tuple[str, ...]] = {
    "en": ("", "s", "es", "ed", "ing", "er", "ly"),
    "es": ("", "s", "es", "o", "a", "os", "as", "ado", "ada"),
    "de": ("", "e", "en", "er", "es", "te", "ten", "ung"),
    "fr": ("", "s", "e", "es", "er", "é", "ée", "ment"),
}


class CandidateFactoryV2Error(ValueError):
    """Kesalahan parameter masukan atau kegagalan gerbang validasi kandidat v2."""


def tokenize_words(text: str) -> list[str]:
    """Pecah teks menjadi token kata UTF-8 Latin secara deterministik."""
    return _WORD_RE.findall(text)


def split_sentences(text: str) -> list[str]:
    """Pecah teks menjadi kalimat tidak kosong berbasis tanda akhir `.`, `!`, `?`."""
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]


def _expand_forbidden_forms(root: str, language: str) -> set[str]:
    clean = root.strip().lower()
    if not clean:
        return set()
    if language == "id":
        stems = {clean}
        if len(clean) > 2 and clean[0] in {"k", "p", "t", "s"}:
            stems.add(clean[1:])
        forms: set[str] = set()
        for pref in _ID_PREFIX_VARIANTS:
            for stem in stems:
                if stem != clean and not any(
                    pref.endswith(p)
                    for p in ("me", "mem", "men", "meng", "meny", "pe", "pem", "pen", "peng", "peny")
                ):
                    continue
                for suff in _ID_SUFFIX_VARIANTS:
                    forms.add(f"{pref}{stem}{suff}")
        return forms
    suffixes = _MULTILINGUAL_INFLECTIONS.get(language, ("", "s"))
    forms = {clean}
    for suff in suffixes:
        forms.add(f"{clean}{suff}")
    return forms


def verify_layered_lang_spec(text: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Pemeriksa kendala mekanis bertingkat deterministik untuk kandidat bahasa v2."""
    if not isinstance(text, str) or not text.strip():
        raise CandidateFactoryV2Error("Teks jawaban bahasa wajib string tidak kosong.")
    if not isinstance(spec, dict):
        raise CandidateFactoryV2Error("Spesifikasi kendala bahasa wajib objek dict.")

    active_layers = list(spec.get("active_layers") or [])
    if not active_layers:
        raise CandidateFactoryV2Error("Spesifikasi bahasa wajib memiliki `active_layers` tidak kosong.")

    language = str(spec.get("language", "id")).strip().lower() or "id"
    words = tokenize_words(text)
    sentences = split_sentences(text)
    lowered_words = [w.lower() for w in words]

    checks: dict[str, Any] = {}
    all_passed = True

    if "word_count" in active_layers:
        exact_words = (spec.get("word_count") or {}).get("exact")
        passed = isinstance(exact_words, int) and len(words) == exact_words
        checks["word_count"] = {"passed": passed, "expected": exact_words, "actual": len(words)}
        all_passed = all_passed and passed

    if "sentence_count" in active_layers:
        exact_sent = (spec.get("sentence_count") or {}).get("exact")
        passed = isinstance(exact_sent, int) and len(sentences) == exact_sent
        checks["sentence_count"] = {"passed": passed, "expected": exact_sent, "actual": len(sentences)}
        all_passed = all_passed and passed

    if "required_phrases" in active_layers:
        req_phrases = list(spec.get("required_phrases") or [])
        missing = [p for p in req_phrases if p not in text]
        passed = len(req_phrases) >= 2 and len(missing) == 0
        checks["required_phrases"] = {"passed": passed, "expected": req_phrases, "missing": missing}
        all_passed = all_passed and passed

    if "forbidden_words" in active_layers:
        roots = [str(r) for r in (spec.get("forbidden_roots") or [])]
        expanded: set[str] = {str(w).lower() for w in (spec.get("forbidden_words") or [])}
        root_map: dict[str, str] = {w: w for w in expanded}
        for root in roots:
            for form in _expand_forbidden_forms(root, language):
                expanded.add(form)
                root_map.setdefault(form, root)
        hits = [
            {"token": words[idx], "matched_root": root_map.get(tok, tok)}
            for idx, tok in enumerate(lowered_words)
            if tok in expanded
        ]
        passed = len(hits) == 0 and (len(roots) > 0 or len(expanded) > 0)
        checks["forbidden_words"] = {"passed": passed, "roots": roots, "hits": hits}
        all_passed = all_passed and passed

    if "required_order" in active_layers:
        req_order = list(spec.get("required_order") or [])
        positions: list[dict[str, Any]] = []
        passed = len(req_order) >= 2
        last_pos = -1
        for fact in req_order:
            pos = text.find(fact)
            positions.append({"fact": fact, "index": pos})
            if pos < 0 or pos <= last_pos:
                passed = False
            if pos >= 0:
                last_pos = pos
        checks["required_order"] = {"passed": passed, "sequence": positions}
        all_passed = all_passed and passed

    if "surface_hygiene" in active_layers:
        hyg = spec.get("surface_hygiene") or {}
        forbid_digits = bool(hyg.get("forbid_digits", True))
        max_word_len = int(hyg.get("max_word_len", 24))
        closing_token = str(hyg.get("closing_token", "")).strip()
        digit_hits = re.findall(r"[0-9]", text) if forbid_digits else []
        long_words = [w for w in words if len(w) > max_word_len]
        closing_ok = True if not closing_token else text.rstrip().endswith(closing_token)
        passed = (not digit_hits) and (not long_words) and closing_ok
        checks["surface_hygiene"] = {
            "passed": passed,
            "digit_hits": digit_hits,
            "long_words": long_words,
            "closing_ok": closing_ok,
            "closing_token": closing_token,
        }
        all_passed = all_passed and passed

    return {
        "schema": LANG_SPEC_V2_SCHEMA,
        "episode_id": str(spec.get("episode_id", "")),
        "language": language,
        "active_layers": active_layers,
        "constraint_count": len(active_layers),
        "passed": all_passed,
        "checks": checks,
    }


def verify_composite_code_spec(episode: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Validasi deterministik kandidat kode berkendala komposit (4 pilar wajib)."""
    instr = episode.get("instruction", "") if isinstance(episode, dict) else ""
    if not isinstance(instr, str) or not instr.strip():
        return {"schema": CODE_SPEC_V2_SCHEMA, "passed": False, "reason": "instruction kosong"}

    required_pillars = {
        "algorithm": str(spec.get("algorithm", "")).strip(),
        "complexity_time": str(spec.get("complexity_time", "")).strip(),
        "complexity_space": str(spec.get("complexity_space", "")).strip(),
        "exact_signature": str(spec.get("exact_signature", "")).strip(),
        "exact_return_format": str(spec.get("exact_return_format", "")).strip(),
    }
    forbidden_tools = [str(t).strip() for t in (spec.get("forbidden_tools") or []) if str(t).strip()]
    missing_fields = [k for k, v in required_pillars.items() if not v]
    if missing_fields or not forbidden_tools:
        return {
            "schema": CODE_SPEC_V2_SCHEMA,
            "passed": False,
            "reason": "metadata komposit tidak lengkap",
            "missing_fields": missing_fields,
        }

    missing_in_prompt = [
        k
        for k, v in (
            ("algorithm", required_pillars["algorithm"]),
            ("complexity_time", required_pillars["complexity_time"]),
            ("complexity_space", required_pillars["complexity_space"]),
            ("exact_signature", required_pillars["exact_signature"]),
            ("exact_return_format", required_pillars["exact_return_format"]),
        )
        if v not in instr
    ]
    missing_forbidden = [t for t in forbidden_tools if t not in instr]
    has_docstring_req = "docstring Bahasa Indonesia" in instr
    passed = (not missing_in_prompt) and (not missing_forbidden) and has_docstring_req
    return {
        "schema": CODE_SPEC_V2_SCHEMA,
        "episode_id": episode.get("id", ""),
        "passed": passed,
        "missing_in_prompt": missing_in_prompt,
        "missing_forbidden_tools": missing_forbidden,
        "has_docstring_req": has_docstring_req,
    }


@dataclass(frozen=True)
class LayeredLangScenario:
    scenario_key: str
    wave_id: str
    language: str
    domain: str
    topic_label: str
    phrases: tuple[str, str]
    forbidden_roots: tuple[str, str, str]
    ordered_facts: tuple[str, str]
    closing_token: str
    sentence_modes: tuple[tuple[str, ...], ...]


LANG_V2_SCENARIOS: tuple[LayeredLangScenario, ...] = (
    # Gelombang Bahasa Indonesia baru (6 domain, 2 mode kalimat masing-masing = 12 variasi dasar)
    LayeredLangScenario(
        scenario_key="id_microgrid",
        wave_id="id_layered",
        language="id",
        domain="mikrogrid_pulau_terpencil",
        topic_label="Laporan Kesiapan Mikrogrid Pulau",
        phrases=("cadangan baterai stabil", "beban puncak teredam"),
        forbidden_roots=("rusak", "padam", "panik"),
        ordered_facts=("inspeksi panel surya pagi", "distribusi malam berjalan aman"),
        closing_token="aman.",
        sentence_modes=(
            (
                "Regu jaga merampungkan inspeksi panel surya pagi sebelum kenaikan konsumsi warga pesisir.",
                "Pengendali cerdas menjaga cadangan baterai stabil sepanjang pergantian awan tebal di teluk.",
                "Skema giliran pompa air membuat beban puncak teredam sehingga distribusi malam berjalan aman.",
            ),
            (
                "Teknisi lapangan memulai inspeksi panel surya pagi untuk memverifikasi sambungan inverter utama.",
                "Sistem penyimpanan mempertahankan cadangan baterai stabil meski tiupan angin laut berubah cepat.",
                "Pemisahan jalur bengkel menjadikan beban puncak teredam menjelang senja tiba.",
                "Catatan operator menutup giliran tugas dengan bukti distribusi malam berjalan aman.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="id_port_coldchain",
        wave_id="id_layered",
        language="id",
        domain="rantai_dingin_pelabuhan",
        topic_label="Protokol Rantai Dingin Pelabuhan",
        phrases=("segel termal utuh", "suhu palka seragam"),
        forbidden_roots=("bocor", "busuk", "batal"),
        ordered_facts=("kalibrasi sensor muatan", "peti kemas siap berangkat"),
        closing_token="berangkat.",
        sentence_modes=(
            (
                "Petugas dermaga menyelesaikan kalibrasi sensor muatan sebelum derek menaikkan kontainer ikan segar.",
                "Pemeriksaan pintu karet membuktikan segel termal utuh serta suhu palka seragam selama pemindahan.",
                "Manifes digital terverifikasi sehingga seluruh rangkaian peti kemas siap berangkat.",
            ),
            (
                "Tim mutu melakukan kalibrasi sensor muatan pada empat sudut ruang simpan berpendingin.",
                "Katup udara bertekanan menjaga segel termal utuh di tengah antrean muat pelabuhan.",
                "Sirkulasi kipas ganda memastikan suhu palka seragam tanpa embun berlebih.",
                "Otoritas karantina menandai semua unit peti kemas siap berangkat.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="id_rural_clinic",
        wave_id="id_layered",
        language="id",
        domain="logistik_klinik_pedesaan",
        topic_label="Ringkasan Distribusi Vaksin Klinik",
        phrases=("rantai dingin terjaga", "kotak pembawa tersegel"),
        forbidden_roots=("cacat", "hilang", "terlambat"),
        ordered_facts=("pendataan botol di pos induk", "layanan posyandu dibuka"),
        closing_token="dibuka.",
        sentence_modes=(
            (
                "Koordinator farmasi menyelesaikan pendataan botol di pos induk sebelum perahu cepat bertolak ke hulu.",
                "Selama pelayaran sungai, sensor saku memastikan rantai dingin terjaga dalam kotak pembawa tersegel.",
                "Bidan desa menerima kiriman tepat waktu sehingga layanan posyandu dibuka.",
            ),
            (
                "Petugas gudang mencatat pendataan botol di pos induk beserta nomor seri tiap kemasan.",
                "Pendingin pasif mempertahankan rantai dingin terjaga meski lintasan darat berbatu.",
                "Kurir menjaga kotak pembawa tersegel hingga tiba di ruang imunisasi.",
                "Setelah verifikasi kartu suhu, layanan posyandu dibuka.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="id_subak_irrigation",
        wave_id="id_layered",
        language="id",
        domain="otomasi_irigasi_subak",
        topic_label="Catatan Pembagian Air Irigasi Subak",
        phrases=("debit pintu tersinkron", "kelembapan petak merata"),
        forbidden_roots=("kering", "banjir", "berebut"),
        ordered_facts=("pembukaan bendung hulu", "musyawarah panen disepakati"),
        closing_token="disepakati.",
        sentence_modes=(
            (
                "Kelompok tani memantau pembukaan bendung hulu setelah hujan mereda di lereng bukit.",
                "Pengatur katup membuat debit pintu tersinkron sehingga kelembapan petak merata di hilir.",
                "Hasil panen awal dicatat rapi lalu musyawarah panen disepakati.",
            ),
            (
                "Pengamat aliran mengawal pembukaan bendung hulu sesuai jadwal tanam serentak.",
                "Saluran bagi menjaga debit pintu tersinkron agar pasokan antarwilayah tetap adil.",
                "Alat ukur tanah membuktikan kelembapan petak merata pada seluruh teras sawah.",
                "Para pekaseh menutup laporan bulanan saat musyawarah panen disepakati.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="id_weather_buoy",
        wave_id="id_layered",
        language="id",
        domain="kalibrasi_pelampung_cuaca",
        topic_label="Audit Telemetri Pelampung Cuaca",
        phrases=("kompas laut akurat", "transmisi satelit jernih"),
        forbidden_roots=("macet", "putus", "hanyut"),
        ordered_facts=("pengujian anemometer dek", "peta prakiraan diterbitkan"),
        closing_token="diterbitkan.",
        sentence_modes=(
            (
                "Kru kapal survei menuntaskan pengujian anemometer dek sebelum unit diturunkan ke selat terbuka.",
                "Kalibrasi ulang menghasilkan kompas laut akurat serta transmisi satelit jernih ke stasiun pantai.",
                "Data arus laut diterima lengkap sehingga peta prakiraan diterbitkan.",
            ),
            (
                "Analis instrumen mencatat pengujian anemometer dek pada kondisi angin tenang.",
                "Penyeimbang magnetik mempertahankan kompas laut akurat menghadapi gelombang panjang.",
                "Antena kedap garam mengirimkan transmisi satelit jernih setiap seperempat jam.",
                "Pusat meteorologi maritim memvalidasi bacaan lalu peta prakiraan diterbitkan.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="id_maritime_archive",
        wave_id="id_layered",
        language="id",
        domain="digitalisasi_arsip_maritim",
        topic_label="Preservasi Peta Pelayaran Nusantara",
        phrases=("kertas katun bebas asam", "pemindaian tanpa sentuhan"),
        forbidden_roots=("sobek", "luntur", "jamur"),
        ordered_facts=("klasifikasi gulungan abad lampau", "katalog publik daring"),
        closing_token="daring.",
        sentence_modes=(
            (
                "Kurator arsip memulai klasifikasi gulungan abad lampau di ruang bertekanan udara saring halus.",
                "Setiap lembar dialasi kertas katun bebas asam untuk mendukung pemindaian tanpa sentuhan.",
                "Citra resolusi tinggi terindeks rapi hingga tersaji pada katalog publik daring.",
            ),
            (
                "Tim konservasi menyusun klasifikasi gulungan abad lampau menurut rute rempah timur.",
                "Map pelindung berbahan kertas katun bebas asam meredam paparan lembap ruang simpan.",
                "Kamera gantung menjalankan pemindaian tanpa sentuhan dengan pencahayaan dingin.",
                "Peneliti sejarah kini menelusuri tautan resmi pada katalog publik daring.",
            ),
        ),
    ),
    # Gelombang Multibahasa baru: 5 bahasa (>= 4 bahasa aturan program): id, en, es, de, fr
    LayeredLangScenario(
        scenario_key="ml_id_rail_signal",
        wave_id="multilingual_wave",
        language="id",
        domain="persinyalan_rel_kota",
        topic_label="Multibahasa ID Sinyal Rel Komuter",
        phrases=("wesel jalur utama", "indikator hijau penuh"),
        forbidden_roots=("tabrak", "anjlok", "buntu"),
        ordered_facts=("pemeriksaan rel fajar", "keberangkatan perdana tepat"),
        closing_token="tepat.",
        sentence_modes=(
            (
                "Petugas lintasan menuntaskan pemeriksaan rel fajar sebelum kereta awal meninggalkan depo.",
                "Sensor optik memeriksa wesel jalur utama serta menyalakan indikator hijau penuh pada panel.",
                "Masinis menerima izin gerak sehingga jadwal keberangkatan perdana tepat.",
            ),
            (
                "Regu sinyal mengawali pemeriksaan rel fajar sepanjang koridor layang selatan.",
                "Pengunci mekanis memastikan wesel jalur utama aman dilewati rangkaian cepat.",
                "Ruang kendali memantau indikator hijau penuh tanpa gangguan arus listrik.",
                "Pintu peron menutup halus dan keberangkatan perdana tepat.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="ml_en_observatory",
        wave_id="multilingual_wave",
        language="en",
        domain="mountain_observatory_calib",
        topic_label="Multilingual EN Mountain Observatory Log",
        phrases=("mirror dome balanced", "clean telemetry stream"),
        forbidden_roots=("crash", "blur", "abort"),
        ordered_facts=("twilight shutter check", "spectrograph capture ready"),
        closing_token="ready.",
        sentence_modes=(
            (
                "Night engineers complete the twilight shutter check before calm ridge winds settle.",
                "Thermal louvers keep the mirror dome balanced and yield a clean telemetry stream.",
                "Guiding stars align smoothly so the spectrograph capture ready.",
            ),
            (
                "Duty astronomers run the twilight shutter check across every auxiliary vent.",
                "Active actuators hold the mirror dome balanced throughout shifting mountain pressure.",
                "Fiber links sustain a clean telemetry stream to the archive vault.",
                "Calibration frames confirm alignment leaving the spectrograph capture ready.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="ml_es_solar_desal",
        wave_id="multilingual_wave",
        language="es",
        domain="desaladora_costera_solar",
        topic_label="Multilingual ES Registro Planta Costera",
        phrases=("membrana limpia estable", "caudal dulce continuo"),
        forbidden_roots=("fallo", "fuga", "corte"),
        ordered_facts=("lectura matinal marina", "tanque comunal lleno"),
        closing_token="lleno.",
        sentence_modes=(
            (
                "Los operadores completan la lectura matinal marina antes de abrir la toma costera.",
                "El filtro solar garantiza membrana limpia estable y caudal dulce continuo hacia el pueblo.",
                "La red distribuye reserva fresca hasta dejar el tanque comunal lleno.",
            ),
            (
                "El turno inicial realiza la lectura matinal marina bajo cielo despejado.",
                "Las bombas mantienen membrana limpia estable sin aumento brusco de salinidad.",
                "Los medidores confirman caudal dulce continuo hacia la cisterna alta.",
                "La válvula central cierra el ciclo dejando el tanque comunal lleno.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="ml_de_alpine_tunnel",
        wave_id="multilingual_wave",
        language="de",
        domain="alpentunnel_lueftung_pruefung",
        topic_label="Multilingual DE Tunnel Lueftungsbericht",
        phrases=("frischluft stabil bleibt", "notlicht klar leuchtet"),
        forbidden_roots=("stau", "rauch", "alarm"),
        ordered_facts=("morgendliche schachtkontrolle", "freie durchfahrt gemeldet"),
        closing_token="gemeldet.",
        sentence_modes=(
            (
                "Techniker beenden die morgendliche schachtkontrolle vor dem Berufsverkehr im Tal.",
                "Drehzahlregler sorgen dass frischluft stabil bleibt und das notlicht klar leuchtet.",
                "Alle Kameras arbeiten sauber sodass eine freie durchfahrt gemeldet.",
            ),
            (
                "Das Wartungsteam startet die morgendliche schachtkontrolle entlang der Ostwand.",
                "Moderne Ventilatoren stellen sicher dass frischluft stabil bleibt.",
                "Batteriebänke sichern dass notlicht klar leuchtet im gesamten Abschnitt.",
                "Nach Abschluss aller Prüfungen wird freie durchfahrt gemeldet.",
            ),
        ),
    ),
    LayeredLangScenario(
        scenario_key="ml_fr_tidal_buoy",
        wave_id="multilingual_wave",
        language="fr",
        domain="station_maregraphique_bretagne",
        topic_label="Multilingual FR Relevé Marégraphique",
        phrases=("capteur marin fiable", "signal horaire net"),
        forbidden_roots=("panne", "erreur", "perte"),
        ordered_facts=("mesure de marée basse", "bulletin côtier publié"),
        closing_token="publié.",
        sentence_modes=(
            (
                "Les gardiens vérifient la mesure de marée basse avant la montée rapide du flot.",
                "La coque étanche protège le capteur marin fiable qui envoie un signal horaire net.",
                "Les données valides circulent jusqu au moment du bulletin côtier publié.",
            ),
            (
                "La brigade valide la mesure de marée basse sur le quai granitique.",
                "Chaque soudure garantit un capteur marin fiable malgré le courant vif.",
                "Le modem solaire diffuse un signal horaire net vers la capitainerie.",
                "Après contrôle complet, le nouveau bulletin côtier publié.",
            ),
        ),
    ),
)


@dataclass(frozen=True)
class CompositeCodeTemplate:
    family: str
    algorithm: str
    complexity_time: str
    complexity_space: str
    forbidden_tools: tuple[str, ...]
    exact_signature: str
    exact_return_format: str
    tie_rule: str
    domain_lead: str
    edge_cases: tuple[str, ...]

    def render_instruction(self, focus_tag: str, selected_edges: tuple[str, ...]) -> str:
        banned = ", ".join(self.forbidden_tools)
        edges_text = "; ".join(selected_edges)
        return (
            f"[KODE V2 | {focus_tag}] {self.domain_lead} "
            f"Implementasikan fungsi Python persis `{self.exact_signature}` menggunakan pustaka standar inti saja. "
            f"Algoritma wajib: {self.algorithm}. "
            f"Batas kompleksitas wajib: waktu {self.complexity_time} dan ruang bantu {self.complexity_space}. "
            f"Larangan alat: DILARANG mengimpor atau memanggil {banned} serta pustaka eksternal apa pun. "
            f"Format keluaran persis: kembalikan {self.exact_return_format} dan naikkan `ValueError` jika masukan tidak valid. "
            f"Aturan deterministik seri/ikatan: {self.tie_rule} "
            f"Tangani eksplisit kasus tepi: {edges_text}. "
            f"Sertakan docstring Bahasa Indonesia."
        )


COMPOSITE_CODE_TEMPLATES: tuple[CompositeCodeTemplate, ...] = (
    CompositeCodeTemplate(
        family="sliding_window_deque",
        algorithm="monotonic deque linear-pass tanpa pemindaian ulang sub-jendela",
        complexity_time="O(n)",
        complexity_space="O(k)",
        forbidden_tools=("heapq", "bisect", "itertools.islice", "numpy"),
        exact_signature="puncak_jendela_monoton(deret_nilai, lebar_k)",
        exact_return_format="list[tuple[int, int]] berisi (indeks_mulai, nilai_puncak)",
        tie_rule="jika nilai maksimum sama dalam satu jendela, pilih indeks paling kanan agar geseran tetap stabil",
        domain_lead="Hitung indeks dan nilai puncak berjalan untuk setiap jendela ukuran tetap pada deret telemetri.",
        edge_cases=(
            "deret kosong mengembalikan daftar kosong []",
            "lebar_k <= 0 atau lebar_k bukan int memicu ValueError",
            "lebar_k > len(deret_nilai) mengembalikan daftar kosong []",
            "seluruh nilai deret identik atau negatif",
        ),
    ),
    CompositeCodeTemplate(
        family="binary_search_monotonic",
        algorithm="pencarian biner atas rentang kapasitas kontinu dengan predikat serakah berurutan",
        complexity_time="O(n log S)",
        complexity_space="O(1)",
        forbidden_tools=("bisect", "itertools", "functools.lru_cache", "numpy"),
        exact_signature="kapasitas_partisi_optimal(beban_paket, maks_kelompok)",
        exact_return_format="dict {'kapasitas_min': int, 'jumlah_kelompok': int}",
        tie_rule="saat predikat terpenuhi pada kapasitas sama, utamakan jumlah kelompok sesedikit mungkin",
        domain_lead="Tentukan kapasitas minimum untuk membagi daftar paket berurutan ke paling banyak M kelompok.",
        edge_cases=(
            "beban_paket kosong dengan maks_kelompok >= 1 mengembalikan {'kapasitas_min': 0, 'jumlah_kelompok': 0}",
            "maks_kelompok <= 0 atau elemen negatif memicu ValueError",
            "maks_kelompok >= len(beban_paket) mengembalikan elemen maksimum",
            "satu elemen jauh lebih besar daripada total elemen lainnya",
        ),
    ),
    CompositeCodeTemplate(
        family="kahn_topo_dag",
        algorithm="algoritma Kahn berbasis min-lex order menggunakan antrean berurutan deterministik",
        complexity_time="O((V + E) log V)",
        complexity_space="O(V + E)",
        forbidden_tools=("heapq", "graphlib", "networkx", "re"),
        exact_signature="urutan_tugas_kahn(daftar_simpul, daftar_sisi)",
        exact_return_format="tuple[str, ...] berisi ID tugas terurut leksikografis pada setiap tingkat siap",
        tie_rule="bila beberapa simpul berderajat-masuk nol bersamaan, ambil ID leksikografis terkecil dahulu",
        domain_lead="Susun eksekusi DAG prasyarat tanpa modul graf atau heap bawaan.",
        edge_cases=(
            "graf kosong mengembalikan tuple kosong ()",
            "siklus atau self-loop memicu ValueError dengan nama simpul siklus",
            "sisi duplikat dinormalisasi tanpa menggandakan derajat masuk",
            "rantai linear 600 simpul diproses secara iteratif tanpa RecursionError",
        ),
    ),
    CompositeCodeTemplate(
        family="interval_weighted_dp",
        algorithm="pemrograman dinamis interval berbobot dengan pencarian indeks pendahulu biner manual",
        complexity_time="O(n log n)",
        complexity_space="O(n)",
        forbidden_tools=("bisect", "heapq", "functools.lru_cache", "itertools"),
        exact_signature="jadwal_bobot_maksimum(interval_item)",
        exact_return_format="dict {'total_bobot': float, 'id_terpilih': tuple[str, ...]}",
        tie_rule="jika total_bobot seri, pilih himpunan dengan jumlah item lebih sedikit lalu tuple id_terpilih terkecil",
        domain_lead="Pilih sub-himpunan interval setengah-terbuka [mulai, selesai) tanpa tumpang tindih dengan bobot terbesar.",
        edge_cases=(
            "interval_item kosong mengembalikan {'total_bobot': 0.0, 'id_terpilih': ()}",
            "mulai >= selesai atau bobot negatif memicu ValueError",
            "interval menyentuh tepat [a, b) dan [b, c) dianggap kompatibel",
            "seluruh bobot bernilai nol tetap menghasilkan pilihan terurut deterministik",
        ),
    ),
    CompositeCodeTemplate(
        family="union_find_rollback",
        algorithm="disjoint-set union by size dengan kompresi jalur iteratif",
        complexity_time="O(m alpha(n))",
        complexity_space="O(n)",
        forbidden_tools=("networkx", "scipy", "itertools", "re"),
        exact_signature="ringkas_klaster_koneksi(simpul_ids, tautan_pasangan)",
        exact_return_format="list[tuple[str, ...]] terurut menurut anggota terkecil tiap komponen",
        tie_rule="setiap komponen diurutkan menaik secara leksikografis dan daftar komponen diurutkan berdasarkan elemen pertama",
        domain_lead="Gabungkan komponen terhubung tak berarah dari daftar simpul dan sisi berpasangan.",
        edge_cases=(
            "simpul_ids kosong mengembalikan daftar kosong []",
            "sisi menunjuk simpul tak dikenal memicu ValueError",
            "simpul terisolasi tanpa tautan tetap muncul sebagai tuple 1-elemen",
            "tautan duplikat dan self-loop ditangani secara idempoten",
        ),
    ),
    CompositeCodeTemplate(
        family="hop_bounded_shortest_path",
        algorithm="relaksasi Bellman-Ford terbatas K-transit dengan salinan lapisan biaya",
        complexity_time="O(k * E)",
        complexity_space="O(V)",
        forbidden_tools=("heapq", "queue", "networkx", "numpy"),
        exact_signature="jalur_biaya_min_transit(daftar_ruas, asal, tujuan, maks_transit)",
        exact_return_format="tuple[int, tuple[str, ...]] atau None jika tidak terjangkau",
        tie_rule="bila total biaya sama, pilih jumlah simpul lebih sedikit lalu urutan rute leksikografis terkecil",
        domain_lead="Cari jalur berbiaya minimum dengan paling banyak maks_transit titik perantara.",
        edge_cases=(
            "asal == tujuan mengembalikan (0, (asal,))",
            "maks_transit < 0 atau biaya negatif memicu ValueError",
            "jalur terpendek langsung melampaui batas transit diabaikan jika melebihi batas",
            "rute multi-ruas dengan beberapa ruas paralel antara pasangan simpul sama",
        ),
    ),
)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lang_prompt_for_spec(
    scenario: LayeredLangScenario,
    sample_text: str,
    active_layers: tuple[str, ...],
    variant_idx: int,
) -> str:
    words_n = len(tokenize_words(sample_text))
    sents_n = len(split_sentences(sample_text))
    # Awalan unik 60+ karakter di depan agar anti-duplikat lintas gelombang & korpus beku terjaga.
    header = f"[{scenario.topic_label} #{variant_idx:02d} ({scenario.language})]"
    parts: list[str] = [f"{header} Susun ringkasan operasional domain `{scenario.domain}` dalam bahasa `{scenario.language}`:"]
    if "word_count" in active_layers:
        parts.append(f"panjang tepat {words_n} kata")
    if "sentence_count" in active_layers:
        parts.append(f"tepat {sents_n} kalimat")
    if "required_phrases" in active_layers:
        parts.append(f'wajib memuat frasa persis "{scenario.phrases[0]}" dan "{scenario.phrases[1]}"')
    if "forbidden_words" in active_layers:
        parts.append(f"dilarang memakai akar kata {', '.join(scenario.forbidden_roots)}")
    if "required_order" in active_layers:
        parts.append(f'urutan fakta wajib: "{scenario.ordered_facts[0]}" sebelum "{scenario.ordered_facts[1]}"')
    if "surface_hygiene" in active_layers:
        parts.append(f'bebas angka digit serta diakhiri tepat oleh token "{scenario.closing_token}"')
    return " ".join(parts) + "."


def _build_lang_wave_candidates(
    *,
    scenarios: tuple[LayeredLangScenario, ...],
    prefix: str,
    count: int,
    constraints_per_episode: int,
    seed: int,
    wave_id: str,
) -> list[dict[str, Any]]:
    active_layers = CONSTRAINT_LAYERS[:constraints_per_episode]
    rng = random.Random(seed)
    pool: list[tuple[LayeredLangScenario, int, tuple[str, ...]]] = []
    for sc in scenarios:
        for m_idx, mode_sents in enumerate(sc.sentence_modes):
            pool.append((sc, m_idx, mode_sents))

    if not pool:
        raise CandidateFactoryV2Error(f"Tidak ada skenario untuk gelombang '{wave_id}'.")

    # Susun variasi deterministik tanpa duplikat jika count > len(pool) dengan variasi urutan/subset mode
    items: list[dict[str, Any]] = []
    for idx in range(count):
        sc, mode_idx, mode_sents = pool[idx % len(pool)]
        cycle = idx // len(pool)
        variant_num = idx + 1
        sample_text = " ".join(mode_sents)
        if cycle > 0:
            # Untuk siklus > 0, variasikan penutup atau tag header agar tetap berbeda unik secara deterministik
            # tanpa merusak kendala frasa/urutan/kebersihan.
            lead_adverbs = {
                "id": ("Catatan resmi:", "Ringkasan shift:", "Pembaruan lapangan:", "Laporan berkala:"),
                "en": ("Shift summary:", "Field brief:", "Status record:", "Daily notice:"),
                "es": ("Informe oficial:", "Resumen técnico:", "Nota operativa:", "Registro diario:"),
                "de": ("Tagesbericht:", "Betriebsnotiz:", "Schichtprotokoll:", "Feldmeldung:"),
                "fr": ("Relevé officiel:", "Note technique:", "Bilan terrain:", "Journal actif:"),
            }[sc.language]
            adv = lead_adverbs[cycle % len(lead_adverbs)]
            if not sample_text.startswith(adv):
                sample_text = f"{adv} {sample_text}"
        ep_id = f"{prefix}{variant_num:03d}"
        words_n = len(tokenize_words(sample_text))
        sents_n = len(split_sentences(sample_text))
        max_w = max((len(w) for w in tokenize_words(sample_text)), default=12) + 2
        spec: dict[str, Any] = {
            "schema": LANG_SPEC_V2_SCHEMA,
            "episode_id": ep_id,
            "wave_id": wave_id,
            "language": sc.language,
            "domain": sc.domain,
            "active_layers": list(active_layers),
            "constraint_count": len(active_layers),
            "word_count": {"exact": words_n},
            "sentence_count": {"exact": sents_n},
            "required_phrases": list(sc.phrases),
            "forbidden_roots": list(sc.forbidden_roots),
            "forbidden_words": [],
            "required_order": list(sc.ordered_facts),
            "surface_hygiene": {
                "forbid_digits": True,
                "max_word_len": max_w,
                "closing_token": sc.closing_token,
            },
        }
        instruction = _lang_prompt_for_spec(sc, sample_text, active_layers, variant_num)
        episode = {
            "id": ep_id,
            "kind": "episode",
            "task_kind": "language",
            "instruction": instruction,
        }
        items.append({"episode": episode, "spec": spec, "sample": sample_text, "wave_id": wave_id, "language": sc.language})
    # Tetap deterministik dengan rng kecil jika kelak diperlukan pengacakan terkendali tanpa duplikasi
    _ = rng.random()
    return items


def _build_code_wave_candidates(
    *,
    prefix: str,
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    items: list[dict[str, Any]] = []
    focus_prefixes = (
        "Reliabilitas",
        "Audit Lintas",
        "Kinerja Ketat",
        "Telemetri Produksi",
        "Presisi Deterministik",
        "Skala Tinggi",
    )
    for idx in range(count):
        tpl = COMPOSITE_CODE_TEMPLATES[idx % len(COMPOSITE_CODE_TEMPLATES)]
        variant_num = idx + 1
        ep_id = f"{prefix}{variant_num:03d}"
        edges = list(tpl.edge_cases)
        # Pilih 2..4 kasus tepi deterministik per episode
        k_edges = 2 + (idx % max(1, len(edges) - 1))
        k_edges = min(k_edges, len(edges))
        picked_edges = tuple(edges[:k_edges])
        if idx >= len(COMPOSITE_CODE_TEMPLATES):
            picked_edges = tuple(rng.sample(edges, k_edges))
        focus_tag = f"{focus_prefixes[idx % len(focus_prefixes)]} #{variant_num:02d} {tpl.family}"
        instruction = tpl.render_instruction(focus_tag, picked_edges)
        spec = {
            "schema": CODE_SPEC_V2_SCHEMA,
            "episode_id": ep_id,
            "wave_id": "code_composite",
            "family": tpl.family,
            "algorithm": tpl.algorithm,
            "complexity_time": tpl.complexity_time,
            "complexity_space": tpl.complexity_space,
            "forbidden_tools": list(tpl.forbidden_tools),
            "exact_signature": tpl.exact_signature,
            "exact_return_format": tpl.exact_return_format,
            "tie_rule": tpl.tie_rule,
            "edge_cases": list(picked_edges),
        }
        episode = {
            "id": ep_id,
            "kind": "episode",
            "task_kind": "code",
            "instruction": instruction,
        }
        items.append({"episode": episode, "spec": spec, "sample": None, "wave_id": "code_composite", "language": "code"})
    return items


def validate_and_filter_v2_candidates(
    candidates: list[dict[str, Any]],
    *,
    frozen_prefixes: dict[str, dict[str, Any]] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Gerbang validasi internal wajib: kandidat gagal cek tidak pernah lolos ke keluaran."""
    seen_instr: set[str] = set()
    seen_prefixes: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for item in candidates:
        ep = item.get("episode")
        spec = item.get("spec")
        sample = item.get("sample")
        wave_id = str(item.get("wave_id", "unknown"))
        language = str(item.get("language", "unknown"))
        ep_id = ep.get("id", "") if isinstance(ep, dict) else ""
        reasons: list[str] = []

        if not isinstance(ep, dict):
            reasons.append("episode_bukan_dict")
        else:
            raw_line = json.dumps(ep, ensure_ascii=False)
            lint_res = lint_lines([raw_line], prefixes=None)
            if not lint_res["valid"]:
                reasons.extend(f"lint:{v['code']}" for v in lint_res["violations"])

            instr = ep.get("instruction", "")
            norm_instr = " ".join(instr.casefold().split()) if isinstance(instr, str) else ""
            if norm_instr in seen_instr:
                reasons.append("duplikat_instruksi_batch")
            prefix60 = norm_instr[:FROZEN_PREFIX_LEN]
            if prefix60 in seen_prefixes:
                reasons.append("benturan_awalan_60_batch")
            if frozen_prefixes and prefix60 in frozen_prefixes:
                reasons.append(f"tumpang_tindih_korpus_beku:{frozen_prefixes[prefix60].get('frozen_file', '')}")

            tk = ep.get("task_kind")
            if tk == "language":
                if not isinstance(sample, str) or not sample.strip():
                    reasons.append("sampel_bahasa_kosong")
                else:
                    ver = verify_layered_lang_spec(sample, spec or {})
                    if not ver["passed"]:
                        failed_checks = [k for k, v in ver["checks"].items() if not v.get("passed")]
                        reasons.append("kendala_bahasa_gagal:" + ",".join(sorted(failed_checks)))
            elif tk == "code":
                ver = verify_composite_code_spec(ep, spec or {})
                if not ver["passed"]:
                    reasons.append("kendala_kode_komposit_gagal")
            else:
                reasons.append("task_kind_tidak_dikenal")

        if reasons:
            rejected.append(
                {
                    "id": str(ep_id),
                    "wave_id": wave_id,
                    "language": language,
                    "reasons": reasons,
                }
            )
            if strict:
                raise CandidateFactoryV2Error(
                    f"Kandidat '{ep_id}' ({wave_id}) gagal validasi internal dan tidak ditulis: {', '.join(reasons)}"
                )
        else:
            norm_instr = " ".join(ep["instruction"].casefold().split())
            seen_instr.add(norm_instr)
            seen_prefixes.add(norm_instr[:FROZEN_PREFIX_LEN])
            accepted.append(item)

    return {"accepted": accepted, "rejected": rejected}


def compute_wave_readiness_census(
    raw_candidates: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    *,
    constraints_per_episode: int,
    multilingual_languages: list[str],
    episodes_sha256: str,
) -> dict[str, Any]:
    """Susun sensus kesiapan per gelombang dan keseluruhan paket v2."""
    by_wave_gen: Counter[str] = Counter()
    by_wave_ok: Counter[str] = Counter()
    by_wave_rej: Counter[str] = Counter()
    langs_by_wave: dict[str, set[str]] = {}

    for item in raw_candidates:
        w = str(item.get("wave_id", "unknown"))
        by_wave_gen[w] += 1
    for item in accepted:
        w = str(item.get("wave_id", "unknown"))
        by_wave_ok[w] += 1
        langs_by_wave.setdefault(w, set()).add(str(item.get("language", "unknown")))
    for item in rejected:
        w = str(item.get("wave_id", "unknown"))
        by_wave_rej[w] += 1

    wave_rows: dict[str, Any] = {}
    for wave_id in sorted(by_wave_gen):
        gen_n = by_wave_gen[wave_id]
        ok_n = by_wave_ok[wave_id]
        rej_n = by_wave_rej[wave_id]
        rate = round(ok_n / gen_n, 4) if gen_n else 0.0
        wave_rows[wave_id] = {
            "generated": gen_n,
            "passed": ok_n,
            "rejected": rej_n,
            "ready_rate": rate,
            "languages": sorted(langs_by_wave.get(wave_id, set())),
            "readiness_status": "READY" if ok_n > 0 and rej_n == 0 else ("PARTIAL" if ok_n > 0 else "REJECTED"),
        }

    return {
        "schema": CENSUS_V2_SCHEMA,
        "constraints_per_episode": constraints_per_episode,
        "multilingual_languages": multilingual_languages,
        "multilingual_language_count": len(multilingual_languages),
        "multilingual_rule_min_languages": MIN_MULTILINGUAL_LANGUAGES,
        "multilingual_rule_satisfied": len(multilingual_languages) >= MIN_MULTILINGUAL_LANGUAGES,
        "total_generated": len(raw_candidates),
        "total_written": len(accepted),
        "total_rejected_not_written": len(rejected),
        "episodes_sha256": episodes_sha256,
        "waves": wave_rows,
        "rejected_items": rejected,
    }


def _load_frozen_prefix_index(frozen_paths: list[Path]) -> dict[str, dict[str, Any]]:
    prefixes: dict[str, dict[str, Any]] = {}
    for path in frozen_paths:
        if not path.is_file():
            raise CandidateFactoryV2Error(f"Berkas korpus beku tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CandidateFactoryV2Error(f"Gagal membaca korpus beku '{path}': {exc}") from exc
        for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                obj = json.loads(raw_line)
            except (json.JSONDecodeError, ValueError) as exc:
                raise CandidateFactoryV2Error(f"JSON korpus beku tidak sah '{path}' baris {line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise CandidateFactoryV2Error(f"Korpus beku '{path}' baris {line_no} wajib objek JSON.")
            prompt_text = obj.get("instruction") if isinstance(obj.get("instruction"), str) else obj.get("prompt")
            if not isinstance(prompt_text, str) or not prompt_text.strip():
                raise CandidateFactoryV2Error(f"Korpus beku '{path}' baris {line_no} tanpa field 'instruction'/'prompt'.")
            meta = {
                "frozen_file": str(path),
                "frozen_id": str(obj.get("id", "")),
                "frozen_line": line_no,
            }
            raw_pref = prompt_text[:FROZEN_PREFIX_LEN]
            norm_pref = " ".join(prompt_text.casefold().split())[:FROZEN_PREFIX_LEN]
            if raw_pref:
                prefixes.setdefault(raw_pref, meta)
            if norm_pref:
                prefixes.setdefault(norm_pref, meta)
    return prefixes


def generate_candidate_v2_bundle(
    output_dir: Path,
    *,
    id_lang_count: int = 12,
    ml_lang_count: int = 10,
    code_count: int = 12,
    constraints_per_episode: int = 5,
    id_prefix: str = DEFAULT_ID_PREFIX,
    ml_prefix: str = DEFAULT_ML_PREFIX,
    code_prefix: str = DEFAULT_CODE_PREFIX,
    languages: tuple[str, ...] = SUPPORTED_MULTILINGUAL_LANGUAGES,
    seed: int = 20261119,
    frozen_paths: list[Path] | None = None,
    injected_candidates: list[dict[str, Any]] | None = None,
    strict_fail_closed: bool = True,
) -> dict[str, Any]:
    """Hasilkan bundel kandidat v2 lengkap (episodes + sidecars + sampel + sensus kesiapan)."""
    if not (MIN_CONSTRAINTS_PER_EPISODE <= constraints_per_episode <= MAX_CONSTRAINTS_PER_EPISODE):
        raise CandidateFactoryV2Error(
            f"--constraints-per-episode wajib dalam rentang {MIN_CONSTRAINTS_PER_EPISODE}..{MAX_CONSTRAINTS_PER_EPISODE}."
        )
    if id_lang_count < 0 or ml_lang_count < 0 or code_count < 0 or (id_lang_count + ml_lang_count + code_count) <= 0:
        raise CandidateFactoryV2Error("Jumlah kandidat minimal satu item > 0.")

    clean_langs = tuple(dict.fromkeys(lang.strip().lower() for lang in languages if lang.strip()))
    if ml_lang_count > 0 and len(clean_langs) < MIN_MULTILINGUAL_LANGUAGES:
        raise CandidateFactoryV2Error(
            f"Aturan program mewajibkan paket multibahasa >= {MIN_MULTILINGUAL_LANGUAGES} bahasa, diterima {len(clean_langs)}."
        )
    unknown_langs = [lang for lang in clean_langs if lang not in SUPPORTED_MULTILINGUAL_LANGUAGES]
    if unknown_langs:
        raise CandidateFactoryV2Error(f"Bahasa tidak didukung pool v2: {', '.join(unknown_langs)}")

    prefixes = [id_prefix, ml_prefix, code_prefix]
    if len(set(prefixes)) != 3 or any(not p or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", p) for p in prefixes):
        raise CandidateFactoryV2Error("Ketiga prefix wajib unik, tidak kosong, dan berkarakter [A-Za-z0-9_-].")

    frozen_map = _load_frozen_prefix_index(frozen_paths) if frozen_paths else None

    raw_candidates: list[dict[str, Any]] = []
    if id_lang_count > 0:
        id_scenarios = tuple(sc for sc in LANG_V2_SCENARIOS if sc.wave_id == "id_layered")
        raw_candidates.extend(
            _build_lang_wave_candidates(
                scenarios=id_scenarios,
                prefix=id_prefix,
                count=id_lang_count,
                constraints_per_episode=constraints_per_episode,
                seed=seed + 1,
                wave_id="id_layered",
            )
        )
    if ml_lang_count > 0:
        ml_scenarios = tuple(
            sc for sc in LANG_V2_SCENARIOS if sc.wave_id == "multilingual_wave" and sc.language in clean_langs
        )
        # Cek bahwa seluruh bahasa terpilih hadir di output bila jumlah cukup.
        if ml_lang_count < len(clean_langs):
            raise CandidateFactoryV2Error(
                f"ml_lang_count={ml_lang_count} lebih kecil daripada jumlah bahasa multibahasa={len(clean_langs)}."
            )
        raw_candidates.extend(
            _build_lang_wave_candidates(
                scenarios=ml_scenarios,
                prefix=ml_prefix,
                count=ml_lang_count,
                constraints_per_episode=constraints_per_episode,
                seed=seed + 2,
                wave_id="multilingual_wave",
            )
        )
    if code_count > 0:
        raw_candidates.extend(
            _build_code_wave_candidates(
                prefix=code_prefix,
                count=code_count,
                seed=seed + 3,
            )
        )
    if injected_candidates:
        raw_candidates.extend(injected_candidates)

    filtered = validate_and_filter_v2_candidates(
        raw_candidates,
        frozen_prefixes=frozen_map,
        strict=strict_fail_closed,
    )
    accepted = filtered["accepted"]
    rejected = filtered["rejected"]
    if not accepted:
        raise CandidateFactoryV2Error("Tidak ada kandidat yang lolos validasi internal; tidak ada berkas yang ditulis.")

    # Verifikasi lintas gelombang dengan linter house repo secara keseluruhan.
    episode_lines = [json.dumps(item["episode"], ensure_ascii=False) for item in accepted]
    lint_result = lint_lines(
        episode_lines,
        frozen_prefixes=frozen_map,
        prefixes=None,
    )
    if not lint_result["valid"]:
        raise CandidateFactoryV2Error(
            "Validasi lint house lintas gelombang gagal: "
            + ", ".join(sorted({v["code"] for v in lint_result["violations"]}))
        )

    episodes_text = "\n".join(episode_lines) + "\n"
    episodes_sha = _sha256_bytes(episodes_text.encode("utf-8"))

    # Tulis berkas hanya sesudah seluruh cek internal lulus.
    output_dir.mkdir(parents=True, exist_ok=True)
    episodes_path = output_dir / "episodes.jsonl"
    lang_specs_path = output_dir / "lang_specs.jsonl"
    code_specs_path = output_dir / "code_specs.jsonl"
    samples_dir = output_dir / "lang_samples"
    census_path = output_dir / "readiness_census.json"

    lang_specs_lines = [json.dumps(item["spec"], ensure_ascii=False) for item in accepted if item["episode"]["task_kind"] == "language"]
    code_specs_lines = [json.dumps(item["spec"], ensure_ascii=False) for item in accepted if item["episode"]["task_kind"] == "code"]

    _atomic_write_text(episodes_path, episodes_text)
    if lang_specs_lines:
        _atomic_write_text(lang_specs_path, "\n".join(lang_specs_lines) + "\n")
    if code_specs_lines:
        _atomic_write_text(code_specs_path, "\n".join(code_specs_lines) + "\n")

    samples_dir.mkdir(parents=True, exist_ok=True)
    for item in accepted:
        if item["sample"] is not None:
            _atomic_write_text(samples_dir / f"{item['episode']['id']}.txt", item["sample"] + "\n")

    ml_covered = sorted({item["language"] for item in accepted if item["wave_id"] == "multilingual_wave"})
    census = compute_wave_readiness_census(
        raw_candidates,
        accepted,
        rejected,
        constraints_per_episode=constraints_per_episode,
        multilingual_languages=ml_covered,
        episodes_sha256=episodes_sha,
    )
    census_payload = {
        "schema": FACTORY_V2_SCHEMA,
        "output_dir": str(output_dir),
        "episodes_path": str(episodes_path),
        "readiness_census": census,
    }
    _atomic_write_text(census_path, json.dumps(census, ensure_ascii=False, indent=2) + "\n")
    return census_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pabrik kandidat corpus v2 (kendala bertingkat, gelombang ID + multibahasa, kode komposit, sensus kesiapan)."
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Direktori keluaran baru untuk bundel v2.")
    parser.add_argument("--id-lang-count", type=int, default=12, help="Jumlah episode gelombang Bahasa Indonesia baru.")
    parser.add_argument("--ml-lang-count", type=int, default=10, help="Jumlah episode gelombang multibahasa (>= 4 bahasa).")
    parser.add_argument("--code-count", type=int, default=12, help="Jumlah episode kode berkendala komposit.")
    parser.add_argument(
        "--constraints-per-episode",
        type=int,
        default=5,
        help="Jumlah lapis kendala per episode bahasa (2..6; default 5).",
    )
    parser.add_argument("--id-prefix", default=DEFAULT_ID_PREFIX, help="Prefix ID gelombang Bahasa Indonesia.")
    parser.add_argument("--ml-prefix", default=DEFAULT_ML_PREFIX, help="Prefix ID gelombang multibahasa.")
    parser.add_argument("--code-prefix", default=DEFAULT_CODE_PREFIX, help="Prefix ID gelombang kode komposit.")
    parser.add_argument(
        "--languages",
        default=",".join(SUPPORTED_MULTILINGUAL_LANGUAGES),
        help="Daftar bahasa gelombang multibahasa dipisah koma (wajib >= 4 bahasa).",
    )
    parser.add_argument("--seed", type=int, default=20261119, help="Seed deterministik.")
    parser.add_argument("--frozen", action="append", type=Path, default=[], help="Berkas korpus beku anti-tumpang-tindih.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        langs = tuple(s.strip().lower() for s in args.languages.split(",") if s.strip())
        summary = generate_candidate_v2_bundle(
            args.output_dir,
            id_lang_count=args.id_lang_count,
            ml_lang_count=args.ml_lang_count,
            code_count=args.code_count,
            constraints_per_episode=args.constraints_per_episode,
            id_prefix=args.id_prefix,
            ml_prefix=args.ml_prefix,
            code_prefix=args.code_prefix,
            languages=langs,
            seed=args.seed,
            frozen_paths=args.frozen or None,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (CandidateFactoryV2Error, InvalidInputError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
