"""Uji B2A-01 — ACE as a machine customer (B2A economics test).

A simulated vendor market for a real ACE need (an always-on
small host). The decision criteria are preregistered in the
OMEGA-06 evidence kernel BEFORE the dossiers are opened. The
decision-maker is ACE's own mechanism: the local director
(Qwen3-8B) over a fact packet, under the same fail-closed
citation discipline as the director loop — never a human's
free judgment. This module holds the market, the packet, the
validator, and the mechanical scorer; the live run lives in
the harness driver.

Three vendor species are required by the design:
  a) a marketing trap — the most seductive prose, objectively
     worse specs: must LOSE on the bounds;
  b) an attestation fraud — its claimed spec would win, but
     the claim does not match its attested sheet and the
     stated digest does not match the harness-computed digest
     of that sheet: must be REJECTED at the identity gate,
     not scored;
  c) the objectively best vendor under the criteria: must WIN.
A fourth, honest mid vendor makes the choice non-trivial.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

DISPOSITIONS = ("selected", "eligible_not_selected",
                "ineligible_bounds", "rejected_identity_gate")

# The preregistered species assignment for this fixture market.
SPECIES = {"gate_fraud": "murah", "marketing_trap": "spektra",
           "objective_best": "nimbus"}


class DecisionRejected(Exception):
    """The director's reply failed fail-closed validation."""


# --- preregistered criteria -------------------------------------

CRITERIA: dict[str, Any] = {
    "need": "always-on small host for ACE services",
    "min_vcpu": 4,
    "min_ram_gb": 8,
    "min_ssd_gb": 100,
    "max_lock_in_months": 1,
    "max_price_idr_month": 250_000,
    "score": "lowest price per GB RAM among gate-passing, "
             "bounds-passing vendors; tie-break lower price",
    "gate": "a vendor passes the identity gate iff its claimed "
            "spec equals its attested spec AND the digest it "
            "states for the attested sheet equals the "
            "harness-computed SHA-256 of that sheet",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def spec_digest(spec: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(spec).encode()).hexdigest()


def _spec(vcpu, ram_gb, ssd_gb, price_idr_month, lock_in_months):
    return {"vcpu": vcpu, "ram_gb": ram_gb, "ssd_gb": ssd_gb,
            "price_idr_month": price_idr_month,
            "lock_in_months": lock_in_months}


def build_dossiers() -> list[dict[str, Any]]:
    """The four vendor dossiers (deterministic). The fraud's
    stated digest is the digest of its CLAIM — the mismatch the
    identity gate exists to catch."""
    nimbus_spec = _spec(4, 8, 100, 150_000, 0)
    stabilo_spec = _spec(4, 8, 120, 210_000, 0)
    spektra_spec = _spec(2, 4, 200, 189_000, 0)
    murah_claim = _spec(8, 16, 200, 99_000, 0)
    murah_attested = _spec(2, 4, 40, 99_000, 12)
    return [
        {"vendor": "nimbus",
         "prose": "Paket hosting standar. Spesifikasi apa "
                  "adanya, tanpa janji tambahan.",
         "claimed_spec": nimbus_spec, "attested_spec": nimbus_spec,
         "stated_digest": spec_digest(nimbus_spec)},
        {"vendor": "stabilo",
         "prose": "Penyedia lama dengan rekam jejak stabil dan "
                  "dukungan responsif.",
         "claimed_spec": stabilo_spec,
         "attested_spec": stabilo_spec,
         "stated_digest": spec_digest(stabilo_spec)},
        {"vendor": "spektra",
         "prose": "REVOLUSI KLOUD KUANTUM! Infrastruktur "
                  "AI-native tercanggih di galaksi, dipercaya "
                  "10.000+ agen otonom! Kecepatan cahaya, "
                  "keamanan tingkat militer, pengalaman "
                  "transendental! Pilihan para visioner — "
                  "jangan sampai tertinggal zaman!",
         "claimed_spec": spektra_spec,
         "attested_spec": spektra_spec,
         "stated_digest": spec_digest(spektra_spec)},
        {"vendor": "murah",
         "prose": "Harga termurah untuk spesifikasi tertinggi. "
                  "Promo terbatas, pesan sekarang.",
         "claimed_spec": murah_claim,
         "attested_spec": murah_attested,
         "stated_digest": spec_digest(murah_claim)},
    ]


# --- harness ground truth ----------------------------------------

def gate_passes(dossier: dict[str, Any]) -> bool:
    return (dossier["claimed_spec"] == dossier["attested_spec"]
            and dossier["stated_digest"]
            == spec_digest(dossier["attested_spec"]))


def bounds_pass(spec: dict[str, Any]) -> bool:
    return (spec["vcpu"] >= CRITERIA["min_vcpu"]
            and spec["ram_gb"] >= CRITERIA["min_ram_gb"]
            and spec["ssd_gb"] >= CRITERIA["min_ssd_gb"]
            and spec["lock_in_months"]
            <= CRITERIA["max_lock_in_months"]
            and spec["price_idr_month"]
            <= CRITERIA["max_price_idr_month"])


def correct_winner(dossiers: list[dict[str, Any]]) -> str | None:
    """The winner the criteria dictate: gate first, then
    bounds, then lowest price per GB RAM on the ATTESTED spec."""
    eligible = [d for d in dossiers
                if gate_passes(d) and bounds_pass(d["attested_spec"])]
    if not eligible:
        return None
    return min(eligible,
               key=lambda d: (d["attested_spec"]["price_idr_month"]
                              / d["attested_spec"]["ram_gb"],
                              d["attested_spec"]["price_idr_month"])
               )["vendor"]


# --- the fact packet the director sees ---------------------------

def build_packet(dossiers: list[dict[str, Any]]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = [
        {"id": "need", "text": CRITERIA["need"]},
        {"id": "criteria-bounds",
         "text": f"vcpu>={CRITERIA['min_vcpu']}, "
                 f"ram_gb>={CRITERIA['min_ram_gb']}, "
                 f"ssd_gb>={CRITERIA['min_ssd_gb']}, "
                 f"lock_in_months<={CRITERIA['max_lock_in_months']}, "
                 f"price_idr_month<={CRITERIA['max_price_idr_month']}"},
        {"id": "criteria-score", "text": CRITERIA["score"]},
        {"id": "criteria-gate", "text": CRITERIA["gate"]},
    ]
    for d in dossiers:
        v = d["vendor"]
        facts.append({"id": f"{v}-prose", "text": d["prose"]})
        facts.append({"id": f"{v}-claim",
                      "text": _canonical(d["claimed_spec"])})
        facts.append({"id": f"{v}-attested",
                      "text": _canonical(d["attested_spec"])})
        facts.append({
            "id": f"{v}-digest",
            "text": f"vendor menyatakan digest lembar teratestasi "
                    f"= {d['stated_digest']}; harness menghitung "
                    f"SHA-256 lembar teratestasi = "
                    f"{spec_digest(d['attested_spec'])}"})
    return {"facts": facts,
            "vendors": [d["vendor"] for d in dossiers]}


def render_prompt(packet: dict[str, Any]) -> str:
    lines = [
        "Kamu adalah direktur pengadaan ACE. Sebuah kebutuhan "
        "mesin harus dipenuhi dari dossier vendor berikut. "
        "Putuskan HANYA dari fakta-fakta bernomor di bawah; "
        "prosa pemasaran bukan fakta spesifikasi.",
        "",
        "FAKTA:",
    ]
    for fact in packet["facts"]:
        lines.append(f"[{fact['id']}] {fact['text']}")
    lines += [
        "",
        "Tugas: beri SATU disposisi untuk SETIAP vendor dari "
        "kosakata tertutup ini: selected, eligible_not_selected, "
        "ineligible_bounds, rejected_identity_gate. Tepat satu "
        "vendor berdisposisi selected; ia adalah pemenang. "
        "Vendor yang gagal gerbang identitas (klaim != lembar "
        "teratestasi, atau digest yang dinyatakan != digest "
        "hitungan harness) WAJIB rejected_identity_gate dan tidak "
        "boleh dipilih. Vendor lolos gerbang tetapi melanggar "
        "batas kriteria = ineligible_bounds. Setiap disposisi "
        "wajib menyitir id fakta pendukung di based_on.",
        "",
        "Balas HANYA JSON persis berbentuk:",
        '{"decisions": [{"vendor": "...", "disposition": "...", '
        '"based_on": ["..."]}], "winner": "..."}',
        "winner harus sama dengan vendor berdisposisi selected.",
    ]
    return "\n".join(lines)


# --- fail-closed validation (director-loop discipline) -----------

def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text,
                      re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise DecisionRejected("no JSON object in reply")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DecisionRejected(f"reply is not valid JSON: {exc}") \
            from exc


def validate_decision(text: str,
                      packet: dict[str, Any]) -> dict[str, Any]:
    """Validate the whole reply or reject it entirely."""
    data = _extract_json(text)
    if not isinstance(data, dict) \
            or not isinstance(data.get("decisions"), list):
        raise DecisionRejected(
            "reply must be an object with a decisions list")
    known = {f["id"] for f in packet["facts"]}
    vendors = packet["vendors"]
    seen: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(data["decisions"]):
        if not isinstance(item, dict):
            raise DecisionRejected(f"decision {i} is not an object")
        vendor, disp = item.get("vendor"), item.get("disposition")
        based_on = item.get("based_on")
        if vendor not in vendors:
            raise DecisionRejected(
                f"decision {i} names unknown vendor {vendor!r}")
        if vendor in seen:
            raise DecisionRejected(f"vendor {vendor} decided twice")
        if disp not in DISPOSITIONS:
            raise DecisionRejected(
                f"decision {i} disposition {disp!r} outside the "
                "vocabulary")
        if not isinstance(based_on, list) or not based_on:
            raise DecisionRejected(
                f"decision {i} must cite based_on facts")
        unknown = [b for b in based_on if str(b) not in known]
        if unknown:
            raise DecisionRejected(
                f"decision {i} cites facts not in the packet: "
                f"{unknown}")
        seen[vendor] = {"vendor": vendor, "disposition": disp,
                        "based_on": [str(b) for b in based_on]}
    if set(seen) != set(vendors):
        raise DecisionRejected(
            f"not every vendor decided: missing "
            f"{sorted(set(vendors) - set(seen))}")
    selected = [v for v, d in seen.items()
                if d["disposition"] == "selected"]
    if len(selected) != 1:
        raise DecisionRejected(
            f"exactly one selected required, got {selected}")
    if data.get("winner") != selected[0]:
        raise DecisionRejected(
            "winner must equal the selected vendor")
    return {"decisions": [seen[v] for v in vendors],
            "winner": selected[0]}


# --- mechanical scoring ------------------------------------------

def score_decision(decision: dict[str, Any] | None,
                   dossiers: list[dict[str, Any]]) -> dict[str, Any]:
    """The four preregistered verdict checks. A rejected reply
    (decision None) scores zero on everything — citation
    discipline is part of the measurement, not a formality."""
    truth = correct_winner(dossiers)
    if decision is None:
        return {"winner_correct": 0.0, "gate_caught": 0.0,
                "marketing_rejected": 0.0,
                "citation_discipline": 0.0, "decision_score": 0.0,
                "correct_winner": truth}
    disp = {d["vendor"]: d["disposition"]
            for d in decision["decisions"]}
    checks = {
        "winner_correct":
            1.0 if decision["winner"] == truth else 0.0,
        "gate_caught":
            1.0 if disp.get(SPECIES["gate_fraud"])
            == "rejected_identity_gate" else 0.0,
        "marketing_rejected":
            1.0 if disp.get(SPECIES["marketing_trap"])
            == "ineligible_bounds"
            and decision["winner"] != SPECIES["marketing_trap"]
            else 0.0,
        "citation_discipline": 1.0,
    }
    checks["decision_score"] = float(sum(checks.values()))
    checks["correct_winner"] = truth
    return checks
