"""Conversational & Operational Bridge for Persistent Cognitive Memory (`memory_bridge.py`).

Wires OMEGA-07 ``CognitiveMemory`` (append-only hash-chained episodic, semantic,
and procedural memory with structural provenance, conflict superseding, privacy
bounds, negative-transfer tracking, and auditable forgetting tombstones) into
``ConversationalEngine``, task episodes, Story Projector, and ACE Web Studio.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .cognitive_memory import CognitiveMemory, ContaminationError, NotFoundError
from .store import OperationalStore

_PRIVATE_HINTS = ("rahasia", "privat", "pribadi", "sensitif")
_CODING_GUARD_WORDS = (
    "pengeluaran", "transaksi", "catat belanja", "catatan belanja",
    "daftar belanja", "keranjang belanja", "keuangan", "dompet",
    "perbaiki", "bug", "error", "refactor", "rapikan",
    "buat ", "buatkan", "bikin", "bikinin", "skrip", "script",
    "program", "aplikasi", "modul", "kalkulator", "csv",
)
_HEARSAY_PREFIXES = (
    "kata teman", "katanya ", "katanya,", "kata orang",
    "gosipnya", "konon ", "misalnya ", "contohnya ",
)
_STOPWORDS_QUERY = frozenset({
    "yang", "tentang", "soal", "di", "ke", "dari", "dan", "atau",
    "itu", "ini", "adalah", "yaitu", "kalau", "bahwa", "ada",
    "saja", "dong", "nih", "sih", "ya", "lagi", "sekarang",
    "apa", "kapan", "siapa", "mana", "dimana", "bagaimana",
})
_KEEP_KU_WORDS = frozenset({"aku", "kamu", "waktu", "sabtu", "minggu", "buku", "suku", "toko", "baku", "saku", "paku"})


def _clean_tail(text: str) -> str:
    return text.strip().strip(".!?\"' ").strip()


def _strip_possessive_token(tok: str) -> str:
    low = tok.lower()
    if low in _KEEP_KU_WORDS:
        return low
    if low.endswith("ku") and len(low) >= 5:
        return low[:-2]
    if low.endswith("mu") and len(low) >= 5 and low not in ("ilmu", "tamu"):
        return low[:-2]
    return low


def normalize_memory_query(raw_q: str) -> tuple[str, bool, bool]:
    """Normalize a recall or forget query into clean tokens.

    Returns ``(normalized_query, is_self_query, is_specific_slot)``.
    """
    clean = _clean_tail(raw_q).lower()
    if not clean or clean in ("semua", "seluruhnya", "semuanya", "privat", "rahasia", "riwayat", "lama"):
        return "", False, False
    if "namaku" in clean or clean in ("nama saya siapa", "siapa nama saya", "nama"):
        return "nama", False, True
    if any(k in clean for k in ("tinggal", "rumahku", "alamatku")):
        return "tempat tinggal", False, True
    if "pekerjaan" in clean or "kerjaan" in clean or "profesiku" in clean:
        return "pekerjaan", False, True
    if "kesukaan" in clean or "suka apa" in clean:
        return "kesukaan", False, True
    if "hobi" in clean:
        return "hobi", False, True
    if "warna favorit" in clean:
        return "warna favorit", False, True
    if "makanan favorit" in clean:
        return "makanan favorit", False, True
    if clean in ("aku", "saya", "diriku", "diri saya", "diriku ini", "profilku", "tentangku"):
        return "pengguna", True, False

    tokens = re.findall(r"[a-z0-9_]+", clean)
    norm_toks: list[str] = []
    for tok in tokens:
        if tok in _STOPWORDS_QUERY or tok in ("privat", "rahasia", "riwayat", "sebelumnya", "lama", "episodik", "semantik", "prosedural"):
            continue
        base = _strip_possessive_token(tok)
        if base in ("aku", "saya", "diriku", "diri") and len(tokens) == 1:
            return "pengguna", True, False
        if base not in norm_toks:
            norm_toks.append(base)
    return " ".join(norm_toks), False, False


def _detect_recall_flags(lower: str) -> tuple[bool, bool, list[str] | None]:
    inc_priv = any(k in lower for k in ("privat", "rahasia", "pribadi"))
    inc_sup = any(k in lower for k in ("riwayat", "sebelumnya", "lama", "konflik", "ralat", "perubahan", "semua versi"))
    kinds: list[str] | None = None
    if "episodik" in lower or "kejadian" in lower or "peristiwa" in lower:
        kinds = ["episodic"]
    elif "semantik" in lower or ("fakta" in lower and "tentang" not in lower):
        kinds = ["semantic"]
    elif "prosedural" in lower or "prosedur" in lower or "langkah kerja" in lower:
        kinds = ["procedural"]
    return inc_priv, inc_sup, kinds


def _match_forget_intent(
    raw_text: str,
    lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any] | None:
    patterns = (
        r"^(?:tolong\s+)?lupakan\s+(?:tentang|soal|fakta|memori|ingatan|kalau|bahwa)\s+(.+)$",
        r"^(?:tolong\s+)?lupakan\s+(.+)$",
        r"^(?:tolong\s+)?hapus\s+(?:ingatan|memori|fakta)\s+(?:tentang\s+|soal\s+)?(.+)$",
        r"^jangan\s+(?:ingat|simpan)\s+(?:lagi\s+)?(?:tentang\s+|soal\s+)?(.+)$",
    )
    for pat in patterns:
        m = re.match(pat, raw_text.strip(), flags=re.IGNORECASE)
        if not m:
            m = re.match(pat, lower, flags=re.IGNORECASE)
        if m:
            target = _clean_tail(m.group(1))
            if not target:
                continue
            return {
                "intent": "MEMORY_FORGET",
                "memory_query": target,
                "normalized_text": norm,
                "constraints": constraints,
                "offline_requested": offline_requested,
                "side_effects_allowed": True,
            }
    return None


def _match_store_intent(
    raw_text: str,
    lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any] | None:
    if any(g in lower for g in ("catat pengeluaran", "catatan pengeluaran", "catat belanja", "catat transaksi")):
        return None
    patterns = (
        r"^(?:tolong\s+)?ingat(?:lah)?\s+(?:bahwa|kalau|ini)?\s*[:,-]?\s*(.+)$",
        r"^(?:tolong\s+)?(?:simpan|catat)\s+(?:di\s+)?(?:memori|ingatanmu|ingatan|fakta)\s*[:,-]?\s*(.+)$",
        r"^(?:tolong\s+)?(?:koreksi|perbarui|ralat)\s+(?:ingatan|memori|fakta)\s*(?:bahwa|kalau)?\s*[:,-]?\s*(.+)$",
    )
    for pat in patterns:
        m = re.match(pat, raw_text.strip(), flags=re.IGNORECASE)
        if m:
            fact_text = _clean_tail(m.group(1))
            if len(fact_text) < 2:
                continue
            is_priv = any(h in lower for h in _PRIVATE_HINTS)
            return {
                "intent": "MEMORY_STORE",
                "memory_text": fact_text,
                "memory_sensitivity": "private" if is_priv else "internal",
                "normalized_text": norm,
                "constraints": constraints,
                "offline_requested": offline_requested,
                "side_effects_allowed": True,
            }
    return None


def _match_audit_or_recall_intent(
    raw_text: str,
    lower: str,
    norm: str,
    constraints: list[str],
    offline_requested: bool,
) -> dict[str, Any] | None:
    audit_phrases = (
        "status memori", "audit memori", "cek kesehatan ingatan",
        "cek kesehatan memori", "cek rantai memori", "riwayat lupa",
        "tombstone memori", "cek status memorimu", "cek status memori",
    )
    if any(p in lower for p in audit_phrases):
        return {
            "intent": "MEMORY_AUDIT",
            "normalized_text": norm,
            "constraints": constraints,
            "offline_requested": offline_requested,
            "side_effects_allowed": False,
        }

    recall_patterns = (
        r"(?:apa\s+(?:saja\s+)?yang\s+(?:kamu|ace)\s+ingat(?:\s+(?:tentang|soal))?\s*)(.*)$",
        r"(?:kamu|ace)\s+ingat\s+(?:tentang|soal)\s+(.+)$",
        r"(?:ingatanmu|memorimu|memori|ingatan)\s+(?:tentang|soal)\s+(.+)$",
        r"(?:cari|cek|tampilkan|daftar)\s+(?:di\s+)?(?:memori|memorimu|ingatan|ingatanmu)\s*(.*)$",
        r"(?:siapa\s+namaku|nama\s+saya\s+siapa|di\s*mana\s+(?:aku|saya)\s+tinggal|apa\s+pekerjaanku|apa\s+kesukaanku|apa\s+hobiku|apa\s+(?:warna|makanan)\s+favoritku|apa\s+jadwalku|kapan\s+jadwal\s+.*)\??$",
    )
    for pat in recall_patterns:
        m = re.search(pat, raw_text.strip(), flags=re.IGNORECASE)
        if m:
            inc_priv, inc_sup, kinds = _detect_recall_flags(lower)
            raw_q = m.group(1) if m.lastindex else raw_text
            clean_q, is_self, is_slot = normalize_memory_query(raw_q)
            if "jadwal" in lower and not clean_q:
                clean_q = "jadwal"
            return {
                "intent": "MEMORY_RECALL",
                "memory_query": clean_q,
                "self_query": is_self,
                "specific_slot": is_slot,
                "include_private": inc_priv,
                "include_superseded": inc_sup,
                "kinds": kinds,
                "normalized_text": norm,
                "constraints": constraints,
                "offline_requested": offline_requested,
                "side_effects_allowed": False,
            }
    return None


def classify_memory_intent(
    raw_text: str,
    norm_text: str,
    constraints: list[str],
    offline_requested: bool,
    *,
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Detect explicit Indonesian memory store, recall, forget, or audit intents."""
    _ = conversation_context
    lower = norm_text.lower().strip()
    if not lower or "siapa namamu" in lower:
        return None

    forget_hit = _match_forget_intent(raw_text, lower, norm_text, constraints, offline_requested)
    if forget_hit is not None:
        return forget_hit

    audit_or_recall = _match_audit_or_recall_intent(raw_text, lower, norm_text, constraints, offline_requested)
    if audit_or_recall is not None:
        return audit_or_recall

    return _match_store_intent(raw_text, lower, norm_text, constraints, offline_requested)


def _extract_profile_triple(raw_text: str) -> dict[str, Any] | None:
    profile_rules: tuple[tuple[str, str, str], ...] = (
        (r"(?:^|\b)(?:namaku|nama\s+(?:ku|saya)|panggil\s+aku)\s+(?:adalah\s+)?([A-Za-z][A-Za-z0-9.'-]*(?:\s+[A-Za-z][A-Za-z0-9.'-]*){0,3})$", "pengguna", "nama"),
        (r"(?:^|\b)(?:aku|saya)\s+(?:sekarang\s+)?(?:tinggal\s+di|pindah\s+(?:tinggal\s+)?ke)\s+(.+)$", "pengguna", "tempat tinggal"),
        (r"(?:^|\b)(?:rumahku|rumah\s+saya|alamatku)\s+(?:sekarang\s+)?(?:(?:pindah|berubah)\s+ke\s+|di\s+)?(.+)$", "pengguna", "tempat tinggal"),
        (r"(?:^|\b)(?:pekerjaanku|pekerjaan\s+saya|profesiku)\s+(?:sekarang\s+)?(?:adalah\s+|sebagai\s+|berubah\s+jadi\s+|pindah\s+jadi\s+)?(.+)$", "pengguna", "pekerjaan"),
        (r"(?:^|\b)(?:aku|saya)\s+(?:bekerja|kerja)\s+(?:sebagai|di)\s+(.+)$", "pengguna", "pekerjaan"),
        (r"(?:^|\b)(?:hobiku|hobi\s+saya)\s+(?:adalah\s+)?(.+)$", "pengguna", "hobi"),
        (r"(?:^|\b)(?:aku|saya)\s+(?:tidak|nggak|gak)\s+suka\s+(.+)$", "pengguna", "ketidaksukaan"),
        (r"(?:^|\b)(?:aku|saya)\s+(?:lebih\s+)?suka\s+(.+)$", "pengguna", "kesukaan"),
        (r"(?:^|\b)warna\s+favoritku\s+(?:adalah\s+)?(.+)$", "pengguna", "warna favorit"),
        (r"(?:^|\b)makanan\s+favoritku\s+(?:adalah\s+)?(.+)$", "pengguna", "makanan favorit"),
    )
    for pat, subj, pred in profile_rules:
        m = re.search(pat, raw_text.strip(), flags=re.IGNORECASE)
        if m:
            obj = _clean_tail(m.group(1))
            if obj and obj.lower() not in ("apa", "siapa", "mana"):
                return {"kind": "semantic", "subject": subj, "predicate": pred, "object": obj}
    return None


def _extract_schedule_or_relation_triple(raw_text: str) -> dict[str, Any] | None:
    m_sched = re.search(
        r"(?:jadwal(?:ku)?\s+(?P<topic>[A-Za-z0-9_]+)?\s*(?:pindah\s+ke|berubah\s+jadi|diubah\s+ke|digeser\s+ke|setiap|tiap|adalah|=)\s*(?P<val>.+))$",
        raw_text.strip(),
        flags=re.IGNORECASE,
    )
    if m_sched:
        raw_topic = _strip_possessive_token(_clean_tail(m_sched.group("topic") or ""))
        val = _clean_tail(m_sched.group("val"))
        if any(w in raw_text.lower() for w in ("tiap ", "setiap ")) and not val.lower().startswith(("tiap ", "setiap ")):
            prefix = "tiap " if "tiap " in raw_text.lower() else "setiap "
            val = prefix + val
        if val:
            subj = "jadwal" if not raw_topic or raw_topic in ("aku", "saya", "pengguna") else f"jadwal {raw_topic}"
            return {"kind": "semantic", "subject": subj, "predicate": "waktu", "object": val}

    m_rel = re.match(
        r"^(?P<subj>[A-Za-z0-9_ ]{2,40}?)\s+(?:itu\s+)?(?:adalah|yaitu|=|sekarang\s+jadi|pindah\s+ke|berubah\s+jadi)\s+(?P<obj>.+)$",
        raw_text.strip(),
        flags=re.IGNORECASE,
    )
    if m_rel:
        subj = " ".join(_strip_possessive_token(t) for t in _clean_tail(m_rel.group("subj")).split())
        obj = _clean_tail(m_rel.group("obj"))
        if subj and obj:
            return {"kind": "semantic", "subject": subj, "predicate": "info", "object": obj}
    return None


def extract_memory_payload(raw_text: str, *, allow_episodic_fallback: bool = True) -> dict[str, Any] | None:
    """Parse an Indonesian statement into structured semantic or episodic memory content."""
    clean = _clean_tail(raw_text)
    if not clean or len(clean) < 3:
        return None
    lower = clean.lower()
    if clean.endswith("?") or any(lower.startswith(p) for p in _HEARSAY_PREFIXES):
        return None
    cleaned_fact = re.sub(r"^(?:sekarang|ternyata|oh\s+iya|ralat)\s+", "", clean, flags=re.IGNORECASE).strip()

    prof = _extract_profile_triple(cleaned_fact)
    if prof is not None:
        return prof

    rel = _extract_schedule_or_relation_triple(cleaned_fact)
    if rel is not None:
        return rel

    if not allow_episodic_fallback:
        return None
    if any(lower.startswith(t) for t in ("kemarin ", "tadi ", "barusan ", "besok ", "nanti ")):
        return {"kind": "episodic", "event": clean, "time_cue": lower.split()[0]}
    return {"kind": "episodic", "event": clean}


_TYPED_PREFIX_TOKENS = frozenset({"jadwal", "pin", "kode", "nomor", "akun", "password", "sandi"})


def _filter_by_relevance_floor(
    results: list[dict[str, Any]],
    query_str: str,
    *,
    strict_compound: bool,
) -> list[dict[str, Any]]:
    if not results or not query_str:
        return results
    q_toks = re.findall(r"[a-z0-9_]+", query_str.lower())
    if len(q_toks) < 2:
        return results
    if strict_compound or q_toks[0] in _TYPED_PREFIX_TOKENS:
        return [r for r in results if int(r.get("relevance", 0)) >= 2]
    return results


class ConversationalMemoryManager:
    """Persistent cognitive memory manager attached to an OperationalStore workspace."""

    def __init__(self, store: OperationalStore):
        self.store = store
        self.memory_dir = store.workspace / "cognitive_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._mem = CognitiveMemory(self.memory_dir)
        self._last_mtime_ns = self._current_log_sig()

    def _current_log_sig(self) -> tuple[int, int]:
        log_path = self.memory_dir / "memory.jsonl"
        if not log_path.is_file():
            return (0, 0)
        st = log_path.stat()
        return (int(st.st_size), int(st.st_mtime_ns))

    def _sync(self) -> CognitiveMemory:
        sig = self._current_log_sig()
        if sig != self._last_mtime_ns:
            self._mem = CognitiveMemory(self.memory_dir)
            self._last_mtime_ns = sig
        return self._mem

    def _refresh_sig(self) -> None:
        self._last_mtime_ns = self._current_log_sig()

    def _active_semantic_map(self, mem: CognitiveMemory) -> dict[tuple[str, str], dict[str, Any]]:
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for rec in mem._records.values():
            if rec.get("kind") == "semantic" and rec.get("status") == "active":
                c = rec["content"]
                subj, pred = c.get("subject"), c.get("predicate")
                if subj is not None and pred is not None:
                    out[(str(subj), str(pred))] = rec
        return out

    def remember_statement(
        self,
        raw_text: str,
        *,
        source_kind: str = "operator",
        source_ref: str | None = None,
        confidence: float = 0.92,
        sensitivity: str = "internal",
        conversation_id: str = "conv_utama",
        allow_episodic_fallback: bool = True,
    ) -> dict[str, Any]:
        """Store a semantic fact or episodic event cleanly and emit honest ACE events."""
        payload = extract_memory_payload(raw_text, allow_episodic_fallback=allow_episodic_fallback)
        if payload is None:
            return {"stored": False, "reason": "not_storable"}

        mem = self._sync()
        kind = payload["kind"]
        content = {k: v for k, v in payload.items() if k != "kind"}
        prev_active = None
        if kind == "semantic":
            prev_active = self._active_semantic_map(mem).get((str(content["subject"]), str(content["predicate"])))

        try:
            rid = mem.remember(
                kind=kind,
                content=content,
                source_kind=source_kind,
                source_ref=source_ref,
                confidence=confidence,
                sensitivity=sensitivity,
            )
        except ContaminationError as exc:
            return {"stored": False, "reason": str(exc)}
        self._refresh_sig()

        superseded = (
            prev_active is not None
            and prev_active["id"] != rid
            and mem._records.get(prev_active["id"], {}).get("status") == "superseded"
        )
        ev_kind = "memory_superseded" if superseded else "memory_saved"
        label = (
            f"{content.get('subject')} {content.get('predicate')}: {content.get('object')}"
            if kind == "semantic"
            else str(content.get("event", ""))[:80]
        )
        self.store.emit_event(
            conversation_id=conversation_id,
            kind=ev_kind,
            status="COMPLETED",
            summary_code=ev_kind,
            technical_detail={
                "record_id": rid,
                "kind": kind,
                "label": label,
                "sensitivity": sensitivity,
                "superseded_id": prev_active["id"] if superseded and prev_active else None,
            },
            verification_passed=bool(mem.audit()["chain_ok"]),
        )
        self.verify_and_promote_frontier()
        return {
            "stored": True,
            "record_id": rid,
            "kind": kind,
            "content": content,
            "sensitivity": sensitivity,
            "superseded": superseded,
            "previous_content": prev_active["content"] if superseded and prev_active else None,
        }

    def observe_conversational_turn(self, user_text: str, *, conversation_id: str = "conv_utama") -> dict[str, Any] | None:
        """Passively extract clear user facts/events from normal Indonesian dialogue."""
        lower = user_text.lower()
        if any(g in lower for g in _CODING_GUARD_WORDS) or len(user_text.split()) > 35:
            return None
        payload = extract_memory_payload(user_text, allow_episodic_fallback=False)
        if payload is None:
            if any(lower.startswith(t) for t in ("kemarin ", "tadi ")):
                return self.remember_statement(
                    user_text,
                    source_kind="operator",
                    confidence=0.85,
                    conversation_id=conversation_id,
                    allow_episodic_fallback=True,
                )
            return None
        return self.remember_statement(
            user_text,
            source_kind="operator",
            confidence=0.9,
            conversation_id=conversation_id,
            allow_episodic_fallback=False,
        )

    def _find_procedure_id(self, mem: CognitiveMemory, domain: str) -> str | None:
        target_name = f"prosedur_{domain}"
        for rid, rec in mem._records.items():
            if rec.get("kind") == "procedural" and rec.get("status") == "active":
                if rec.get("content", {}).get("name") == target_name:
                    return rid
        return None

    def _has_task_episode(self, mem: CognitiveMemory, task_id: Any, status: Any) -> str | None:
        for rid, rec in mem._records.items():
            if rec.get("kind") == "episodic" and rec.get("status") == "active":
                c = rec.get("content", {})
                if c.get("task_id") == task_id and c.get("status") == status:
                    return rid
        return None

    def record_task_episode(
        self,
        task: dict[str, Any] | None,
        *,
        domain: str,
        conversation_id: str = "conv_utama",
    ) -> dict[str, Any] | None:
        """Record an evidence-anchored episodic and procedural outcome for a verified task."""
        if not task:
            return None
        _ = conversation_id
        mem = self._sync()
        task_id = task.get("task_id")
        status = task.get("status")
        ver_sum = task.get("verification_summary") or {}
        passed = bool(status == "COMPLETED")
        ev_blob = json.dumps(
            {
                "task_id": task_id,
                "title": task.get("title_id"),
                "domain": domain,
                "status": status,
                "artifacts": task.get("artifacts", []),
                "verification_summary": ver_sum,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        digest = mem.anchor_evidence(ev_blob)
        ep_id = self._has_task_episode(mem, task_id, status)
        if ep_id is None:
            ep_id = mem.remember(
                kind="episodic",
                content={
                    "task_id": task_id,
                    "task": task.get("title_id", domain),
                    "domain": domain,
                    "status": status,
                    "outcome": ver_sum.get("sample_output") or status,
                    "goal": task.get("normalized_goal", ""),
                },
                source_kind="evidence",
                source_ref=digest,
                confidence=0.98 if passed else 0.75,
            )
        proc_id = self._find_procedure_id(mem, domain)
        if proc_id is None:
            proc_id = mem.remember(
                kind="procedural",
                content={
                    "name": f"prosedur_{domain}",
                    "domain": domain,
                    "steps": ["analisis permintaan", "tulis/perbaiki atomik", "uji subproses & receipt"],
                },
                source_kind="evidence",
                source_ref=digest,
                confidence=0.95,
            )
        mem.record_outcome(proc_id, context=domain, success=passed)
        self._refresh_sig()
        self.verify_and_promote_frontier()
        return {"episodic_id": ep_id, "procedural_id": proc_id, "digest": digest}

    def recall_memories(
        self,
        query: str = "",
        *,
        kinds: list[str] | None = None,
        context: str | None = None,
        limit: int = 10,
        token_budget: int = 2000,
        include_private: bool = False,
        include_superseded: bool = False,
        specific_slot: bool = False,
    ) -> dict[str, Any]:
        """Run bounded OMEGA-07 recall across active records."""
        mem = self._sync()
        raw_q = query.strip()
        norm_q, is_self, slot_hint = normalize_memory_query(raw_q) if raw_q else ("", False, False)
        use_slot = specific_slot or slot_hint
        effective_q = norm_q if raw_q else ""

        primary = mem.recall(
            effective_q,
            kinds=kinds,
            context=context,
            limit=limit,
            token_budget=token_budget,
            include_private=include_private,
            include_superseded=include_superseded,
        )
        results = list(primary["results"])
        if is_self or effective_q == "pengguna":
            extra = mem.recall(
                "aku saya",
                kinds=kinds,
                context=context,
                limit=limit,
                token_budget=token_budget,
                include_private=include_private,
                include_superseded=include_superseded,
            )
            seen = {r["id"] for r in results}
            for item in extra["results"]:
                if item["id"] not in seen and len(results) < limit:
                    results.append(item)
                    seen.add(item["id"])
        elif results:
            results = _filter_by_relevance_floor(results, effective_q, strict_compound=use_slot)
            if use_slot and results:
                top_rel = max(int(r.get("relevance", 0)) for r in results)
                if top_rel >= 2:
                    results = [r for r in results if int(r.get("relevance", 0)) == top_rel]
        return {
            "results": results,
            "truncated": primary["truncated"],
            "considered": max(primary["considered"], len(results)),
            "returned": len(results),
        }

    def forget_by_query(self, query: str, *, reason: str = "diminta pengguna lewat chat", conversation_id: str = "conv_utama") -> dict[str, Any]:
        """Find highest-relevance matching records (including private) and replace with tombstones."""
        mem = self._sync()
        norm_q, _, _ = normalize_memory_query(query)
        search_q = norm_q or query.strip()
        if not search_q:
            return {"forgotten_count": 0, "tombstones": [], "audit": mem.audit()}
        found = mem.recall(search_q, limit=12, include_private=True, include_superseded=True)
        candidates = _filter_by_relevance_floor(found.get("results", []), search_q, strict_compound=True)
        tombstones: list[dict[str, Any]] = []
        if candidates:
            max_rel = max(int(r.get("relevance", 0)) for r in candidates)
            targets = [r for r in candidates if int(r.get("relevance", 0)) == max_rel] if max_rel > 0 else candidates
            for rec in targets:
                if rec["id"] in mem._records:
                    tombstones.append(mem.forget(rec["id"], reason=reason))
        self._refresh_sig()
        if tombstones:
            self.store.emit_event(
                conversation_id=conversation_id,
                kind="memory_forgotten",
                status="COMPLETED",
                summary_code="memory_forgotten",
                technical_detail={"count": len(tombstones), "query": query[:60], "reason": reason},
                verification_passed=bool(mem.audit()["chain_ok"]),
            )
        return {"forgotten_count": len(tombstones), "tombstones": tombstones, "audit": mem.audit()}

    def forget_by_id(self, record_id: str, *, reason: str = "dihapus pengguna lewat Web Studio") -> dict[str, Any]:
        """Destroy one specific record by ID and emit an audited tombstone."""
        mem = self._sync()
        if record_id not in mem._records:
            raise NotFoundError(record_id)
        tombstone = mem.forget(record_id, reason=reason)
        self._refresh_sig()
        self.store.emit_event(
            kind="memory_forgotten",
            status="COMPLETED",
            summary_code="memory_forgotten",
            technical_detail={"count": 1, "record_id": record_id, "reason": reason},
            verification_passed=bool(mem.audit()["chain_ok"]),
        )
        return {"tombstone": tombstone, "audit": mem.audit()}

    def audit_report(self) -> dict[str, Any]:
        """Return CognitiveMemory integrity audit report."""
        mem = self._sync()
        return mem.audit()

    def get_summary(self) -> dict[str, Any]:
        """Compact memory summary suitable for /api/status and badges."""
        rep = self.audit_report()
        return {
            "chain_ok": rep["chain_ok"],
            "active_records": rep["active_records"],
            "superseded_records": rep["superseded_records"],
            "tombstones_count": len(rep["tombstones"]),
            "anchored_evidence": rep["anchored_evidence"],
        }

    def list_snapshot(self, *, include_private: bool = False, include_superseded: bool = True) -> dict[str, Any]:
        """Return safe inspection snapshot for Web Studio UI."""
        mem = self._sync()
        active_res = mem.recall("", limit=50, token_budget=6000, include_private=include_private, include_superseded=False)
        all_res = mem.recall("", limit=50, token_budget=6000, include_private=include_private, include_superseded=include_superseded)
        superseded = [r for r in all_res["results"] if r.get("status") == "superseded"]
        audit = mem.audit()
        return {
            "audit": audit,
            "summary": self.get_summary(),
            "active_records": active_res["results"],
            "superseded_records": superseded,
            "tombstones": audit["tombstones"],
        }

    def format_record_line(self, rec: dict[str, Any]) -> str:
        """Format one memory record concisely in Indonesian."""
        kind = rec.get("kind", "episodic")
        c = rec.get("content", {})
        src = (rec.get("source") or {}).get("kind", "operator")
        tags = []
        if rec.get("status") == "superseded":
            tags.append("digantikan")
        if rec.get("stale"):
            tags.append("usang")
        if rec.get("guess"):
            tags.append("dugaan model")
        if rec.get("negative_transfer_risk"):
            tags.append("risiko transfer negatif")
        if rec.get("sensitivity") == "private":
            tags.append("privat")
        meta_str = f" [{', '.join(tags)}]" if tags else ""
        if kind == "semantic":
            body = f"**{c.get('subject')}** ({c.get('predicate')}): {c.get('object')}"
        elif kind == "procedural":
            body = f"**{c.get('name')}** (domain `{c.get('domain', '-')}`)"
        else:
            body = str(c.get("event") or f"{c.get('task', '')} -> {c.get('outcome', '')}").strip()
        return f"- `{kind}` (`{src}`){meta_str}: {body}"

    def build_prompt_context(self, query_text: str) -> str:
        """Build bounded non-private recalled memory summary for prompt conditioning."""
        found = self.recall_memories(query_text, limit=3, token_budget=400, include_private=False)
        if not found["results"]:
            found = self.recall_memories("", limit=3, token_budget=300, include_private=False)
        if not found["results"]:
            return "belum ada memori relevan"
        return "; ".join(self.format_record_line(r).lstrip("- ") for r in found["results"])

    def verify_and_promote_frontier(self) -> bool:
        """Verify live hash-chain & memory integrity before marking frontier KNOWN_AND_TESTED."""
        rep = self.audit_report()
        if not rep.get("chain_ok"):
            return False
        existing = {f["capability_id"]: f for f in self.store.list_frontier()}
        cur = existing.get("cap_memori_jangka_panjang")
        if cur and cur.get("status") == "KNOWN_AND_TESTED":
            return True
        proof = hashlib.sha256(json.dumps(rep, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        self.store.set_frontier_capability(
            capability_id="cap_memori_jangka_panjang",
            name_id="Memori Jangka Panjang (Episodik, Semantik, Prosedural & Lupa Terukur)",
            category="memori",
            status="KNOWN_AND_TESTED",
            evidence_ref=f"cognitive_memory:chain_ok:{proof}",
        )
        return True

    def _format_recall_reply(self, frame: dict[str, Any]) -> str:
        q = str(frame.get("memory_query", "")).strip()
        res = self.recall_memories(
            q,
            kinds=frame.get("kinds"),
            limit=8,
            include_private=bool(frame.get("include_private")),
            include_superseded=bool(frame.get("include_superseded")),
            specific_slot=bool(frame.get("specific_slot")),
        )
        if not res["results"]:
            audit = self.audit_report()
            extra = (
                f" Sebagai catatan jujur, ada {len(audit['tombstones'])} catatan tombstone yang sebelumnya diminta untuk dilupakan."
                if audit["tombstones"]
                else ""
            )
            target_label = f" tentang `{q}`" if q else ""
            return f"Secara jujur, saat ini aku belum punya ingatan aktif{target_label}.{extra}"
        lines = "\n".join(self.format_record_line(r) for r in res["results"])
        trunc = (
            f"\n_(Menampilkan {res['returned']} dari {res['considered']} memori cocok sesuai batas anggaran token.)_"
            if res["truncated"]
            else ""
        )
        return f"Ini yang kuingat dari **Memori Jangka Panjang**:\n{lines}{trunc}"

    def handle_chat_intent(self, frame: dict[str, Any], raw_text: str, conversation_id: str) -> tuple[str, dict[str, Any] | None]:
        """Execute MEMORY_STORE, MEMORY_RECALL, MEMORY_FORGET, or MEMORY_AUDIT intents."""
        intent = frame.get("intent")
        if intent == "MEMORY_STORE":
            sens = str(frame.get("memory_sensitivity", "internal"))
            res = self.remember_statement(
                str(frame.get("memory_text") or raw_text),
                source_kind="operator",
                confidence=0.95,
                sensitivity=sens,
                conversation_id=conversation_id,
            )
            if not res.get("stored"):
                return f"Maaf, aku belum bisa menyimpan ingatan itu karena `{res.get('reason', 'format tidak valid')}`.", None
            priv_note = " dengan perlindungan **privat**" if sens == "private" else ""
            rec_view = {"kind": res["kind"], "content": res["content"], "source": {"kind": "operator"}, "sensitivity": sens}
            if res.get("superseded") and res.get("previous_content"):
                prev_obj = res["previous_content"].get("object", "")
                return (
                    f"Sip, aku sudah memperbarui ingatanku{priv_note}! Fakta lama (*{prev_obj}*) "
                    f"kutandai **digantikan (`superseded`)** tanpa menghapus jejak riwayatnya.\n"
                    f"{self.format_record_line(rec_view)}"
                ), None
            return (
                f"Baik, sudah kusimpan permanen ke **Memori Jangka Panjang**{priv_note} (ID `{res['record_id']}`):\n"
                f"{self.format_record_line(rec_view)}"
            ), None

        if intent == "MEMORY_FORGET":
            q = str(frame.get("memory_query", "")).strip()
            res = self.forget_by_query(q, conversation_id=conversation_id)
            if res["forgotten_count"] == 0:
                return f"Tidak kutemukan ingatan aktif yang cocok dengan `{q}`, jadi tidak ada yang kuhapus.", None
            tomb_ids = ", ".join(f"`{t['record_id']}`" for t in res["tombstones"][:4])
            return (
                f"Berhasil! Sebanyak **{res['forgotten_count']} ingatan** terkait `{q}` sudah kuhancurkan isinya "
                f"dan dicatat lewat **tombstone teraudit** ({tomb_ids}).\n"
                f"- Rantai hash memori: `{'VALID' if res['audit']['chain_ok'] else 'RUSAK'}`\n"
                f"- Total memori aktif tersisa: **{res['audit']['active_records']}**"
            ), None

        if intent == "MEMORY_AUDIT":
            rep = self.audit_report()
            return (
                "Berikut laporan kesehatan **Memori Jangka Panjang (OMEGA-07)**:\n"
                f"- Integritas rantai hash: `{'VALID' if rep['chain_ok'] else 'TIDAK VALID'}` ({rep['events']} event)\n"
                f"- Memori aktif: **{rep['active_records']}** | Tergantikan (`superseded`): **{rep['superseded_records']}**\n"
                f"- Tombstone lupa teraudit: **{len(rep['tombstones'])}** | Bukti terjangkar: **{rep['anchored_evidence']}**\n"
                f"- Memori kedaluwarsa: **{len(rep['expired_record_ids'])}**"
            ), None

        return self._format_recall_reply(frame), None
