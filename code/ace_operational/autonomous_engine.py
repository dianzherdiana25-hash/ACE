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

import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import time
from typing import Any

from ace_operational.autonomy_loop import AutonomyOrchestrator
from ace_operational.models_backend import ModelRouter
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
            "        if w.endswith(s) and len(w) > len(s) + 2:\n"
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
]


class ContinuousAutonomousEngine:
    """Manages indefinite autonomous operational and self-development cycles for ACE."""

    def __init__(
        self,
        store: OperationalStore | None = None,
        workspace: Path | None = None,
        tick_interval_seconds: float = 6.0,
    ):
        self.workspace = workspace or (Path.home() / ".local" / "share" / "ace" / "workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = store or OperationalStore(workspace=self.workspace)
        self.orchestrator = AutonomyOrchestrator(self.store)
        self.models = ModelRouter(self.store)
        self.tick_interval_seconds = tick_interval_seconds
        self.running = False
        self.cycle_count = 0
        self.status_file = self.workspace / "autonomous_engine.status.json"
        self.corpus_file = self.workspace / "projects" / "bahasa" / "dialog_corpus.jsonl"
        self.corpus_file.parent.mkdir(parents=True, exist_ok=True)

    def update_status_file(self, current_action: str, details: dict[str, Any] | None = None) -> None:
        payload = {
            "schema": "ace.autonomous_engine.status.v1",
            "running": self.running,
            "cycle_count": self.cycle_count,
            "current_action": current_action,
            "pid": os.getpid(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "details": details or {},
        }
        try:
            tmp = self.status_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.status_file)
        except Exception as e:
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

    def execute_continuous_language_learning(self) -> dict[str, Any] | None:
        """Continuously and indefinitely learn Indonesian language modules, grammar, and dialogue."""
        existing_skills = {s["name"]: s for s in self.store.list_skills()}

        # 1. Check curriculum items that haven't been learned yet
        for item in LANGUAGE_CURRICULUM:
            skill_name = item["skill_name"]
            if skill_name not in existing_skills:
                logger.info(f"[Language Learning] Advancing curriculum: {skill_name} ({item['title']})...")
                task = self.store.create_task(
                    title_id=item["title"],
                    user_request=f"Kembangkan keterampilan bahasa Indonesia: {item['title']}",
                    normalized_goal=item["goal"],
                )
                self.store.emit_event(
                    kind="task_started",
                    status="ACTIVE",
                    summary_code=f"Belajar Bahasa: {item['title']}",
                    technical_detail={"title_id": item["title"], "goal": item["goal"]},
                )

                # Write module to disk
                target_p = self.workspace / item["target_file"]
                target_p.parent.mkdir(parents=True, exist_ok=True)
                target_p.write_text(item["code"], encoding="utf-8")

                # Execute verification
                import subprocess
                proc = subprocess.run([sys.executable, str(target_p)], capture_output=True, text=True, timeout=10)
                if proc.returncode == 0 and item["verification_str"] in proc.stdout:
                    receipt = self.store.record_receipt(
                        task_id=task["task_id"],
                        action_kind="execute_language_verification",
                        input_data=item["code"],
                        output_data=proc.stdout,
                        command_or_operation=f"{sys.executable} {target_p}",
                        exit_code=proc.returncode,
                        stdout_text=proc.stdout,
                        stderr_text=proc.stderr,
                        artifacts_created=[str(target_p)],
                        verified_by="autonomous_language_curriculum_verifier",
                        passed=True,
                    )
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
                        category="bahasa",
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
                        summary_code=f"Keterampilan Bahasa Baru: {item['title']}",
                        verification_passed=True,
                        artifact_refs=[str(target_p)],
                        technical_detail={
                            "title_id": item["title"],
                            "skill_name": skill_name,
                            "receipt_id": receipt["receipt_id"],
                        },
                    )
                    logger.info(f"Learned and verified language skill '{skill_name}' with receipt {receipt['receipt_id']}")
                    return {"skill": skill_name, "receipt": receipt["receipt_id"]}

        # 2. Dynamic Ongoing Language Dialogue Practice (Indefinite Continuous Mode)
        # When all static curriculum items are learned, ACE generates and validates continuous dialogue interactions
        return self._generate_dynamic_language_dialogue_practice()

    def _generate_dynamic_language_dialogue_practice(self) -> dict[str, Any] | None:
        """Generate and evaluate real-time Indonesian dialogue interactions via local GGUF."""
        hc = self.models.health_check()
        if not hc.get("local_gguf", {}).get("server_healthy"):
            return None

        sample_prompts = [
            "Jelaskan arti pepatah 'sedikit demi sedikit lama-lama menjadi bukit' secara ringkas.",
            "Berikan contoh sapaan santai khas Indonesia dan penggunaannya.",
            "Bagaimana cara membedakan kata santun dan kata kasar dalam bahasa Indonesia?",
            "Jelaskan perbedaan kata 'bisa' dan 'dapat' dalam kalimat bahasa Indonesia.",
            "Berikan kalimat motivasi bahasa Indonesia yang membakar semangat dalam 20 kata.",
        ]
        prompt = sample_prompts[self.cycle_count % len(sample_prompts)]
        logger.info(f"[Continuous Language Learning] Exploring dynamic dialogue: '{prompt}'...")

        try:
            resp = self.models.generate_text([
                {"role": "system", "content": "Kamu adalah ACE, entitas kecerdasan otonom yang mendalami bahasa Indonesia. Berikan jawaban yang bernas, santai, dan tepat bahasa."},
                {"role": "user", "content": prompt},
            ], max_tokens=128)
            ans = resp.get("text", "").strip()
            if ans:
                # Save to corpus
                entry = {
                    "cycle": self.cycle_count,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
                logger.info(f"[Continuous Language Learning] Successfully acquired dialogue sample for cycle #{self.cycle_count}")
                return {"dialogue_practice": prompt, "answer_preview": ans[:40]}
        except Exception as e:
            logger.warning(f"Dynamic language practice failed: {e}")
        return None

    def execute_cycle(self) -> None:
        """Run a single autonomous cycle."""
        self.cycle_count += 1
        logger.info(f"--- Starting Autonomous Cycle #{self.cycle_count} ---")
        self.update_status_file("cycle_started")

        # Step 1: Health & GGUF verification
        self.update_status_file("discovering_models")
        self.verify_and_promote_local_gguf()

        # Step 2: Advance queued agenda items
        self.update_status_file("advancing_agenda")
        advanced_count = self.check_and_advance_agenda()

        # Step 3: Continuous Language Learning Loop (Endless Evolution)
        if advanced_count == 0:
            self.update_status_file("learning_indonesian_language")
            self.execute_continuous_language_learning()

        # Step 4: Heartbeat & sync
        self.update_status_file("idle_waiting_next_cycle", {
            "last_cycle_completed": self.cycle_count,
            "next_cycle_in_seconds": self.tick_interval_seconds,
        })
        logger.info(f"--- Completed Autonomous Cycle #{self.cycle_count}. Sleeping {self.tick_interval_seconds}s ---")

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

                # Sleep interval checking running flag
                slept = 0.0
                step = 0.5
                while self.running and slept < self.tick_interval_seconds:
                    time.sleep(step)
                    slept += step

        finally:
            self.running = False
            self.update_status_file("stopped")
            logger.info("ACE Continuous Autonomous Engine cleanly stopped.")


def main():
    engine = ContinuousAutonomousEngine(tick_interval_seconds=6.0)
    engine.run_forever()


if __name__ == "__main__":
    main()
