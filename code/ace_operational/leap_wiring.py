"""Wiring live lompatan EVO 0031–0040 ke siklus engine.

Aktivasi 2026-11-20 atas perintah langsung pemilik ("aktifkan
sampai yang terbaru... semua"). Satu modul integrasi: tiap fungsi
``step_*`` menjalankan satu kemampuan lompatan pada data live
engine dan mengembalikan ringkasan JSON untuk summary siklus.
Pemanggil (``autonomous_engine.execute_cycle``, Step 3d) membungkus
setiap step dengan try/except — pola Step 3c — jadi kegagalan satu
lompatan tidak pernah membunuh siklus; ia tercatat sebagai
``{"status": "error"}`` pada summary.

Gate: ``ACE_LEAPS=1`` pada proses engine. Tanpa flag, tidak ada
perilaku live yang berubah.

Peta step → lompatan:
- step_checkpoint  → EVO 0034 (checkpoint per siklus, rantai hash)
- step_recall      → EVO 0031 + 0017 (konsolidasi memori + probe
                     recall hybrid/reranker di jalur live)
- step_house       → EVO 0034 (model dunia rumah + perencana +
                     probe regresi berkala + buku insiden)
- step_director    → EVO 0033 + 0040 (konteks receipt ke observasi
                     director, lipat duplikat live, penantang,
                     antrean evolusi persisten, audit invarian)
- step_practice    → EVO 0032 (penjadwal praktik berjarak +
                     generator tugas dari pola gagal)
- step_projects    → EVO 0035 (lapisan proyek persisten; proyek
                     perdana = perbaikan recall EVO 0031)
- step_self        → EVO 0038 + 0039 (model diri dari kustodi,
                     buku hipotesis, pertanyaan kuriositas)
- step_organs      → EVO 0036 (smoke organ berkala + rekomendasi
                     adopsi; replikasi rumah kedua tetap menunggu
                     bundle EVO 0016)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Modul-modul tools/ hidup di akar repo; ace.py hanya menaruh code/
# di sys.path. Sisipkan akar repo sekali, di sini, agar wiring bisa
# mengimpornya dari proses engine mana pun.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _state(engine: Any) -> dict[str, Any]:
    path = engine.workspace / "leap_state.json"
    state = _read_json(path, {})
    return state if isinstance(state, dict) else {}


def _save_state(engine: Any, state: dict[str, Any]) -> None:
    _write_json(engine.workspace / "leap_state.json", state)


# ------------------------------------------------------------------
# EVO 0034 — checkpoint rantai hash per siklus
# ------------------------------------------------------------------

def step_checkpoint(engine: Any) -> dict[str, Any]:
    from ace_operational import step_checkpoint as sc

    path = engine.workspace / "step_checkpoints.jsonl"
    result = sc.save_step_checkpoint(
        path,
        step_id=f"cycle_{engine.cycle_count}",
        state={
            "cycle": engine.cycle_count,
            "lang_cursor": getattr(engine, "_lang_cursor", None),
            "tech_cursor": getattr(engine, "_tech_cursor", None),
        },
    )
    chain = sc.verify_and_load_checkpoints(path)
    return {"status": "ok", "checkpoint": result.get("step_id"),
            "chain_len": len(chain)}


# ------------------------------------------------------------------
# EVO 0031 + 0017 — konsolidasi memori + probe recall live
# ------------------------------------------------------------------

def _bridge_embedder():
    """Embedder semantik via bridge (POST /v1/embeddings) — EVO 0017 M3.

    Mengembalikan None bila ACE_BRAIN_BRIDGE_URL tak terkonfigurasi;
    pemanggil wajib fail-closed ke kanal leksikal saat embedder None
    atau panggilannya gagal (mis. anggaran embedding harian habis).
    Cache per instance: satu teks unik = satu panggilan bridge.
    """
    base = os.environ.get("ACE_BRAIN_BRIDGE_URL", "").rstrip("/")
    if not base:
        return None
    cache: dict[str, list[float]] = {}

    def embed(text: str) -> list[float]:
        if text not in cache:
            req = urllib.request.Request(
                base + "/v1/embeddings",
                data=json.dumps({"input": text}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            cache[text] = [float(v) for v in payload["data"][0]["embedding"]]
        return cache[text]

    return embed


def step_recall(engine: Any) -> dict[str, Any]:
    from ace_operational import memory_consolidation as mc
    from ace_operational import recall_candidates as rc
    from ace_operational import recall_reranker as rr

    ws: Path = engine.workspace
    log_path = ws / "cognitive_memory" / "memory.jsonl"
    out: dict[str, Any] = {"status": "ok"}
    episodes: list[dict[str, Any]] = []
    if log_path.is_file():
        distilled = mc.distill_memory_log(
            log_path, snapshot_dir=ws / "memory_snapshots")
        _write_json(ws / "semantic_memory.json", distilled)
        out["consolidated_clusters"] = distilled["consolidated_cluster_count"]
        out["active_episodes"] = distilled["total_active_episodes"]
        episodes, _ = mc.load_active_episodes(log_path)

    # Probe pengantaran: query = tema gap OPEN; kandidat dari episode
    # memori lewat jalur hybrid (leksikal + provenance + semantik bila
    # embedder bridge tersedia — EVO 0017 M3) lalu reranker.
    gaps = engine.store.list_gaps(status="OPEN")
    delivered = 0
    probed = 0
    semantic_hits = 0
    embedder = _bridge_embedder()
    for gap in gaps[:10]:
        # Kunci nyata baris gaps: error_type/missing_skill_or_tool/
        # description_id (kunci lama gap_type/skill_name/title tidak
        # pernah ada di store — query probe selalu kosong sebelum ini).
        query = " ".join(str(gap.get(k) or "") for k in
                         ("error_type", "missing_skill_or_tool",
                          "description_id", "gap_type", "skill_name",
                          "title", "description"))
        if not query.strip():
            continue
        probed += 1

        class _Store:
            def list_records(self_inner):  # noqa: N805
                return episodes

        channels = {
            "lexical": rc.lexical_candidates(query, _Store(), limit=10),
            "provenance": rc.provenance_candidates(query, _Store(), limit=10),
        }
        if embedder is not None:
            try:
                # Batas 60 rekaman: mengikat biaya embedding per probe
                # (anggaran peran embedding harian terbatas).
                class _EmbStore:
                    def list_records(self_inner):  # noqa: N805
                        return episodes[:60]

                emb = rc.embedding_candidates(query, _EmbStore(), embedder, limit=10)
                if emb:
                    channels["embedding"] = emb
                    semantic_hits += 1
            except Exception:
                pass  # fail-closed: kanal leksikal+provenance tetap jalan
        merged = rc.merge_candidates(channels, limit=10)
        ranked = rr.rerank_candidates(merged, {}, limit=5)
        if ranked and float(ranked[0].get("score") or 0) > 0:
            delivered += 1
    rate = (delivered / probed) if probed else None
    _append_jsonl(ws / "recall_probe.jsonl", {
        "at": _now_iso(), "cycle": engine.cycle_count,
        "probed_gaps": probed, "delivered": delivered, "rate": rate,
        "semantic_probes": semantic_hits})
    out["probe"] = {"probed": probed, "delivered": delivered, "rate": rate,
                    "semantic_probes": semantic_hits}
    return out


# ------------------------------------------------------------------
# EVO 0034 — model dunia rumah + perencana + probe regresi + insiden
# ------------------------------------------------------------------

def step_house(engine: Any) -> dict[str, Any]:
    from ace_operational import house_model as hm
    from tools import cycle_planner_sim as cps
    from tools import incident_book as ib

    ws: Path = engine.workspace
    now = _now_iso()
    open_gaps = len(engine.store.list_gaps(status="OPEN"))
    waiting = sum(1 for t in engine.store.list_tasks(limit=200)
                  if t.get("status") == "WAITING_FOR_DEPENDENCY")
    telemetry = {
        "engine": {"updated_at": now, "pid": getattr(engine, "_pid", None),
                   "cycle": engine.cycle_count},
        "store": {"updated_at": now, "open_gaps": open_gaps,
                  "waiting_tasks": waiting},
        "bridge": {"updated_at": now,
                   "transport_failures": getattr(
                       engine, "_bridge_transport_failures", 0)},
    }
    model = hm.build_house_world_model(telemetry, now=now)
    _write_json(ws / "house_model.json", model)
    # Perencana memakai skema dunianya sendiri; adaptor ini memetakan
    # keadaan live (kegagalan bridge, antrean) ke skema itu.
    bridge_failures = getattr(engine, "_bridge_transport_failures", 0)
    planner_world = {
        "house_state": "healthy" if bridge_failures == 0 else "sick",
        "bridge_health": {"ok": bridge_failures == 0},
        "budgets": {"roles": {}},
    }
    steps = [
        {"step_id": "advancing_agenda", "role": "front", "critical": True},
        {"step_id": "mixed_autonomous_learning", "role": "coder", "critical": True},
        {"step_id": "director_loop", "role": "front", "critical": False},
        {"step_id": "director_execution", "role": "front", "critical": False},
        {"step_id": "leap_steps", "role": "front", "critical": False},
    ]
    plan = cps.plan_cycle_steps(planner_world, steps)
    _write_json(ws / "cycle_plan.json", plan)
    out: dict[str, Any] = {"status": "ok", "open_gaps": open_gaps,
                           "waiting_tasks": waiting}

    # Probe regresi tiap 50 siklus terhadap pak tersegel AG29; solver
    # = jalur recall leksikal live atas episode memori.
    if engine.cycle_count % 50 == 0:
        from ace_operational import memory_consolidation as mc
        from ace_operational import recall_candidates as rc
        from tools import regression_probe as rp

        pack = _REPO_ROOT / "tools" / "fixtures" / "heldout_regression_tasks_v1.jsonl"
        log_path = ws / "cognitive_memory" / "memory.jsonl"
        episodes: list[dict[str, Any]] = []
        if log_path.is_file():
            episodes, _ = mc.load_active_episodes(log_path)

        class _Store:
            def list_records(self_inner):  # noqa: N805
                return episodes

        def solver(task: dict[str, Any]) -> Any:
            query = str(task.get("query") or task.get("prompt") or "")
            cands = rc.lexical_candidates(query, _Store(), limit=1)
            return cands[0] if cands else {}

        report = rp.run_probe_and_append_series(
            pack, ws / "regression_series.jsonl", solver,
            incident_path=ws / "regression_incidents.jsonl")
        out["regression_probe"] = {
            "score": report.get("score"), "tasks": report.get("task_count")}
        if report.get("incident"):
            ib.record_incident(
                ws / "incidents.jsonl",
                incident_id=f"regression-{engine.cycle_count}",
                kind="regression_drop",
                cause="skor probe regresi turun melewati ambang",
                remediation="periksa seri regresi dan perubahan recall terakhir",
                recovery_evidence="menunggu probe berikutnya")
    return out


# ------------------------------------------------------------------
# EVO 0033 + 0040 — director belajar dari receipt, lipat live,
# penantang, antrean evolusi persisten, audit invarian eksekusi
# ------------------------------------------------------------------

def step_director(engine: Any) -> dict[str, Any]:
    from ace_operational import director_receipt_context as drc
    from ace_operational import evolution_proposals as ep
    from tools import director_challenger as dc
    from tools import director_fold as df
    from tools import execution_invariants as ei

    ws: Path = engine.workspace
    out: dict[str, Any] = {"status": "ok"}
    receipts_path = ws / "director_exec_receipts.jsonl"

    # Konteks receipt untuk observasi director siklus berikutnya.
    if receipts_path.is_file():
        ctx = drc.build_receipt_context(receipts_path, None)
        engine._director_context_block = drc.render_context_block(ctx)
        out["receipt_context_events"] = ctx.get("total_events")

    # Lipat duplikat WAITING berbasis based_on yang sama (pola
    # gelombang robustness, kini memakai perencana lipat AG72):
    # duplikat → CANCELLED dengan penanda folded_into; keeper tetap.
    waiting = [t for t in engine.store.list_tasks(limit=200)
               if t.get("kind") == "director_proposal"
               and t.get("status") == "WAITING_FOR_DEPENDENCY"]
    rows = []
    for t in waiting:
        proposal = (t.get("checkpoint") or {}).get("proposal") or {}
        rows.append({"task_id": t["task_id"], "status": t["status"],
                     "created_at": t.get("created_at") or _now_iso(),
                     "based_on": list(proposal.get("based_on") or [])})
    folded_count = 0
    if rows:
        folded = df.fold_proposals(rows)
        for group in folded["groups"]:
            for dup_id in group["duplicates"]:
                task = engine.store.get_task(dup_id)
                if task is None:
                    continue
                engine.store.update_task(
                    dup_id, status="CANCELLED",
                    checkpoint={"folded_into": group["representative"],
                                "fold_reason": "duplicate_based_on"})
                folded_count += 1
        if folded_count:
            for line in df.build_fold_receipt_lines(folded):
                _append_jsonl(ws / "director_fold_receipts.jsonl", line)
    out["folded_duplicates"] = folded_count

    # Penantang atas proposal WAITING terbaru: tantangan dicatat
    # sebagai anotasi, bukan perubahan status.
    if waiting:
        newest = waiting[0]
        proposal = (newest.get("checkpoint") or {}).get("proposal") or {}
        facts = {
            "verified_refs": [g["gap_id"] for g in
                              engine.store.list_gaps(status="OPEN")],
            "prior_proposals": [
                {"task_id": t["task_id"],
                 "based_on": list(((t.get("checkpoint") or {})
                                   .get("proposal") or {}).get("based_on") or [])}
                for t in waiting[1:]],
        }
        verdict = dc.challenge_proposal(
            {"task_id": newest["task_id"], **proposal}, facts)
        challenges = verdict.get("challenges") or []
        if challenges:
            _append_jsonl(ws / "director_challenges.jsonl", {
                "at": _now_iso(), "task_id": newest["task_id"],
                "challenges": challenges})
            out["challenged"] = newest["task_id"]

    # Antrean evolusi persisten (EVO 0040): proposal director yang
    # MASIH WAITING (daftar disegarkan sesudah pelipatan) dan belum
    # terdaftar masuk antrean ratifikasi modul evolution_proposals;
    # status antrean disimpan sebagai JSON di workspace.
    waiting = [t for t in engine.store.list_tasks(limit=200)
               if t.get("kind") == "director_proposal"
               and t.get("status") == "WAITING_FOR_DEPENDENCY"]
    queue_path = ws / "evolution_queue.json"
    saved = _read_json(queue_path, [])
    queue = ep.RatificationQueue()
    known_ids: set[str] = set()
    if isinstance(saved, list):
        for entry in saved:
            if isinstance(entry, dict) and entry.get("proposal_id"):
                known_ids.add(str(entry["proposal_id"]))
    submitted = 0
    for t in waiting:
        if t["task_id"] in known_ids:
            continue
        proposal = (t.get("checkpoint") or {}).get("proposal") or {}
        anchors = [str(b) for b in (proposal.get("based_on") or []) if str(b).strip()]
        if not anchors:
            continue  # antrean evolusi menolak proposal tanpa jangkar fakta
        candidate = {
            "proposal_id": t["task_id"],
            "title": proposal.get("title") or t.get("title_id") or t["task_id"],
            "benefit_hypothesis": proposal.get("rationale") or "tanpa rasional tercatat",
            "measurement_method": "receipt eksekusi Kelas A + verdict terkait gap",
            "cost": "satu slot eksekusi director",
            "risk": {"level": "low",
                     "mitigation": "hanya Kelas A berreceipt; cap harian 3; kill-switch env"},
            "fact_anchors": anchors,
        }
        try:
            queue.submit(candidate)
            submitted += 1
        except Exception:
            continue
    entries = queue.list_entries()
    _write_json(queue_path, entries)
    out["evolution_queue"] = {"submitted": submitted, "total": len(entries)}

    # Audit invarian eksekusi (EVO 0036) atas receipt Kelas A.
    if receipts_path.is_file():
        receipts = []
        for line in receipts_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    receipts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        report = ei.check_execution_invariants(receipts, receipts, daily_cap=3)
        holds = bool(report.get("all_invariants_hold", True))
        out["invariants_ok"] = holds
        if not holds:
            _append_jsonl(ws / "invariant_violations.jsonl", {
                "at": _now_iso(), "cycle": engine.cycle_count,
                "report": report})
    return out


# ------------------------------------------------------------------
# EVO 0032 — penjadwal praktik berjarak + tugas dari pola gagal
# ------------------------------------------------------------------

def step_practice(engine: Any) -> dict[str, Any]:
    from ace_operational import practice_scheduler as ps
    from tools import failure_taskgen as ftg

    ws: Path = engine.workspace
    gaps = engine.store.list_gaps()
    histories = [{
        "gap_id": g["gap_id"],
        "skill_name": g.get("skill_name") or "",
        "gap_type": g.get("gap_type") or "",
        "status": g.get("status"),
        "occurrence_count": g.get("occurrence_count") or 0,
        "created_at": g.get("created_at"),
        "updated_at": g.get("updated_at"),
    } for g in gaps]

    class _GapStore:
        def list_gap_histories(self_inner):  # noqa: N805
            return histories

    schedule = ps.schedule_gap_practice(
        _GapStore(), now=datetime.now(timezone.utc))
    _write_json(ws / "practice_schedule.json", schedule)
    out: dict[str, Any] = {"status": "ok", "scheduled_gaps": len(schedule)}

    # Tugas baru hanya untuk gap yang occurrence-nya NAIK sejak
    # siklus leap terakhir (pola gagal yang masih hidup), maks 1/siklus.
    state = _state(engine)
    seen_occ: dict[str, int] = state.get("gap_occurrences", {})
    grown = [g for g in gaps
             if g.get("status") == "OPEN"
             and int(g.get("occurrence_count") or 0) > int(seen_occ.get(g["gap_id"], 0))]
    created = 0
    if grown:
        g = grown[0]
        fingerprint = {
            "fingerprint_id": f"gap-{g['gap_id']}",
            "gap_id": g["gap_id"],
            "skill_name": g.get("skill_name") or "",
            "gap_type": g.get("gap_type") or "",
            "occurrence_count": g.get("occurrence_count") or 0,
        }
        try:
            generated = ftg.generate_and_validate_tasks([fingerprint])
            for task_def in (generated.get("accepted_tasks") or [])[:1]:
                engine.store.create_task(
                    kind="learning_practice",
                    title_id=str(task_def.get("title") or f"praktik {g['gap_id']}"),
                    user_request=json.dumps(task_def, ensure_ascii=False),
                    normalized_goal=str(task_def.get("goal") or g["gap_id"]),
                    model_backend="leap_wiring/failure_taskgen",
                    priority=5,
                    checkpoint={"stage": "failure_taskgen",
                                "gap_id": g["gap_id"], "task": task_def},
                    hold_for_review=False,
                )
                created += 1
        except Exception:
            created = 0
    state["gap_occurrences"] = {
        g["gap_id"]: int(g.get("occurrence_count") or 0) for g in gaps}
    _save_state(engine, state)
    out["practice_tasks_created"] = created
    return out


# ------------------------------------------------------------------
# EVO 0035 — lapisan proyek persisten (proyek perdana: recall 0031)
# ------------------------------------------------------------------

class _ProjectFileStore:
    """Adapter ProjectStore di atas berkas JSON per proyek."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, project_id: str) -> Path:
        return self._root / f"{project_id}.json"

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        data = _read_json(self._path(project_id), None)
        return data if isinstance(data, dict) else None

    def save_project(self, project_id: str, data: Any) -> None:
        _write_json(self._path(project_id), dict(data))

    def verify_ref(self, ref: str) -> bool:
        if ref.startswith("file:"):
            return Path(ref[5:]).is_file()
        return bool(ref)


def step_projects(engine: Any) -> dict[str, Any]:
    from ace_operational import project_layer as pl

    ws: Path = engine.workspace
    store = _ProjectFileStore(ws / "projects")
    pid = "evo0031-recall-repair"
    if store.get_project(pid) is None:
        pl.create_project(store, project_id=pid,
                          title="Perbaikan pengantaran recall EVO 0031/0017",
                          milestones=[
                              {"milestone_id": "wiring_live",
                               "title": "Wiring lompatan live di engine",
                               "gate_refs": [f"file:{ws / 'semantic_memory.json'}"]},
                              {"milestone_id": "ablation_m2",
                               "title": "Ablasi M2 dijalankan ulang di store nyata",
                               "gate_refs": [f"file:{ws / 'ablation_m2_summary.json'}"]},
                              {"milestone_id": "verdict_g2",
                               "title": "Putusan G2 ulang tersegel (M3)",
                               "gate_refs": [f"file:{ws / 'g2_verdict.json'}"]},
                          ])
    project = store.get_project(pid) or {}
    advanced: list[str] = []
    for ms in project.get("milestones", []):
        mid = ms.get("milestone_id")
        if not mid or ms.get("status") in ("completed", "done", "selesai"):
            continue
        refs = list(ms.get("gate_refs") or [])
        if refs and all(store.verify_ref(r) for r in refs):
            try:
                pl.start_milestone(store, project_id=pid, milestone_id=mid)
            except Exception:
                pass
            try:
                pl.verify_milestone_gate(
                    store, project_id=pid, milestone_id=mid,
                    gate_evidence={"gate_refs": refs})
                advanced.append(mid)
            except Exception:
                pass
        break  # tonggak berurutan: nilai satu per siklus
    return {"status": "ok", "project": pid, "advanced": advanced}


# ------------------------------------------------------------------
# EVO 0038 + 0039 — model diri, buku hipotesis, kuriositas
# ------------------------------------------------------------------

class _HypothesisFileStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _all(self) -> dict[str, Any]:
        data = _read_json(self._path, {})
        return data if isinstance(data, dict) else {}

    def save_hypothesis(self, record: Any) -> None:
        data = self._all()
        data[str(record["hypothesis_id"])] = dict(record)
        _write_json(self._path, data)

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None:
        rec = self._all().get(hypothesis_id)
        return dict(rec) if isinstance(rec, dict) else None

    def list_hypotheses(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._all().values() if isinstance(r, dict)]


def step_self(engine: Any) -> dict[str, Any]:
    from ace_operational import hypothesis_book as hb
    from ace_operational import self_model as sm
    from tools import curiosity_questions as cq

    ws: Path = engine.workspace
    out: dict[str, Any] = {"status": "ok"}

    builder = sm.SelfModelBuilder()
    receipts = ws / "director_exec_receipts.jsonl"
    if receipts.is_file():
        out["receipts_ingested"] = builder.ingest_receipts_jsonl(receipts)
    memory_log = ws / "cognitive_memory" / "memory.jsonl"
    if memory_log.is_file():
        out["memory_events_ingested"] = builder.ingest_memory_chain_jsonl(memory_log)
    payload = builder.build()
    sm.validate_self_model_payload(payload)
    _write_json(ws / "self_model.json", payload)

    book = hb.HypothesisBook(_HypothesisFileStore(ws / "hypotheses.json"))
    hid = "recall-pool-cleanup"
    if book._store.get_hypothesis(hid) is None:
        book.register(
            hid,
            cause="Ablasi EVO 0017 M1: kolam kandidat tercemar riwayat tugas COMPLETED",
            measurable_prediction="Ablasi M2 (kolam dibersihkan) mengalahkan delta legacy -0,164 dan anchored -0,145",
            falsification_condition="Delta M2 tetap negatif pada tugas yang sama di store nyata",
            confidence=0.6, domain="recall")
    m2_file = ws / "ablation_m2_summary.json"
    if m2_file.is_file():
        rec = book._store.get_hypothesis(hid) or {}
        if rec.get("status") == "terdaftar":
            try:
                book.start_test(hid, experiment_id="evo0017-m2")
            except Exception:
                pass
    out["hypotheses"] = len(book._store.list_hypotheses())

    world = _read_json(ws / "house_model.json", {})
    asked_path = ws / "curiosity_asked.json"
    asked = _read_json(asked_path, [])
    questions = cq.generate_curiosity_questions(
        world if isinstance(world, dict) else {},
        {"hypotheses": book._store.list_hypotheses()},
        asked_questions=asked if isinstance(asked, list) else [])
    new_q = questions.get("questions") or []
    for q in new_q:
        _append_jsonl(ws / "curiosity_questions.jsonl",
                      {"at": _now_iso(), "cycle": engine.cycle_count, "q": q})
    if isinstance(asked, list):
        asked.extend(str(q.get("question") or q) for q in new_q)
        _write_json(asked_path, asked[-200:])
    out["curiosity_new"] = len(new_q)
    return out


# ------------------------------------------------------------------
# EVO 0036 — smoke organ berkala + rekomendasi adopsi berbasis skor
# ------------------------------------------------------------------

def step_organs(engine: Any) -> dict[str, Any]:
    from ace_operational import brain_endpoints
    from tools import organ_smoke as osm

    ws: Path = engine.workspace
    pack = osm.default_smoke_pack()[:3]

    def transport(organ: str, task: dict[str, Any]) -> dict[str, Any]:
        prompt = str(task.get("prompt") or task.get("question") or "")
        reply = brain_endpoints.chat_structured(
            organ, [{"role": "user", "content": prompt}],
            max_tokens=256, check_health=False)
        return {"output": reply.content, "brain_of_origin": reply.brain_of_origin}

    report = osm.run_organ_smoke(["front", "coder"], pack, transport)
    _write_json(ws / "organ_smoke.json", report)
    scores = report.get("scores") or report.get("per_organ") or {}
    best = None
    if isinstance(scores, dict) and scores:
        def _score(v: Any) -> float:
            if isinstance(v, dict):
                return float(v.get("mean_score") or v.get("score") or 0)
            return float(v or 0)
        best = max(scores, key=lambda k: _score(scores[k]))
    prev = _read_json(ws / "organ_recommendation.json", {})
    if best and (not isinstance(prev, dict) or prev.get("recommended") != best):
        _write_json(ws / "organ_recommendation.json", {
            "at": _now_iso(), "recommended": best,
            "basis": "skor smoke organ tertinggi pada putaran terakhir",
            "scores": scores})
    return {"status": "ok", "smoked_organs": ["front", "coder"],
            "best": best}


# ------------------------------------------------------------------
# EVO 0043 — AG125: candidate census over workspace candidate packs (%25)
# ------------------------------------------------------------------

def step_candidate_census(engine: Any) -> dict[str, Any]:
    try:
        from tools import candidate_census as cc

        ws = Path(engine.workspace)
        out_path = ws / "candidate_census.json"
        files: list[Path] = []
        for fname in ("candidates.jsonl", "candidate_intake.jsonl", "discriminating_intake.jsonl"):
            p = ws / fname
            if p.is_file():
                files.append(p)
        cand_dir = ws / "candidates"
        if cand_dir.is_dir():
            for p in sorted(cand_dir.glob("*.jsonl")):
                if p not in files:
                    files.append(p)

        if not files:
            skipped = {
                "status": "skipped",
                "reason": "no candidate files in workspace",
                "checked_at": _now_iso(),
            }
            _write_json(out_path, skipped)
            return skipped

        reports: list[dict[str, Any]] = []
        ready_count = 0
        for f in files:
            rep = cc.census_file(f)
            if (rep.get("readiness") or {}).get("ready"):
                ready_count += 1
            reports.append(rep)

        payload = {
            "status": "ok",
            "checked_at": _now_iso(),
            "cycle": getattr(engine, "cycle_count", 0),
            "files_audited": len(reports),
            "ready_files": ready_count,
            "reports": reports,
        }
        _write_json(out_path, payload)
        return {
            "status": "ok",
            "files_audited": len(reports),
            "ready_files": ready_count,
        }
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

