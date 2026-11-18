"""EVO 0007 package runner (preregistration PR #311, S9.2).

The measured subject is ACE's pattern-recall path; the treatment
is the context kind (POLA / RECEIPT / SHAM / KOSONG) and the
registered API organ set is the executing / judge instrument.
This module holds the package's deterministic logic plus a thin
transport binding to the vault-connector helper scripts; it is
import-safe and fully testable with fake transports. No live run
happens before the preregistration freezes (hub-ratified PR).

Discipline carried from the successor package (PR #311 S7):
stop-on-first-error per phase, error rows quarantined by the
caller, brain-of-origin recorded on every call, delivery recorded
first-class per episode (the EVO 0005 lesson).
"""
from __future__ import annotations

import json
import random
import statistics
import subprocess
import tempfile
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Callable

# Organ roles per preregistration S2. Proposer != validator,
# crossed per task kind; the judge organ is fixed for the whole
# package (judge identity = instrument identity).
# Model amendment (hub-ratified 2026-11-18): the Gemini roles
# named gemini-2.5-pro at freeze, but that model is retired for
# this account (HTTP 404 "no longer available to new users",
# measured live); all three Gemini roles (language proposer,
# code validator, distiller) move to gemini-3-flash-preview -
# the honest consequence is recorded in the amendment: flash
# class is weaker than pro, the calibration inside this package
# absorbs it (the band derives from this amended instrument
# set and every arm runs under the same instrument).
ORGAN_ROLES = {
    "code": {
        "proposer": ("groq", "qwen/qwen3.8-27b"),
        "validator": ("gemini", "gemini-3-flash-preview"),
    },
    "language": {
        "proposer": ("gemini", "gemini-3-flash-preview"),
        "validator": ("groq", "openai/gpt-oss-120b"),
    },
}
JUDGE_ORGAN = ("cloudflare", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
DISTILLER_ORGAN = ("gemini", "gemini-3-flash-preview")

DEFAULT_BAND = (45.0, 75.0)
MIN_PROBE = 8
MIN_LANGUAGE = 4
SPREAD_FLAG = 50.0
DELIVERY_GATE = 0.75
SCREEN_BUDGET_FROZEN = 60          # frozen pools, preregistration S3
SCREEN_BUDGET_FACTORY_WAVES = 2    # x12 heavier candidates each

Transport = Callable[[str, str, str, int], str]
# transport(provider, model, prompt, max_tokens) -> completion text


# ------------------------------------------------------------------
# Judge output parsing (semantics: judge v3, fail-closed)
# ------------------------------------------------------------------

def first_json_object(text: str) -> dict:
    """Extract the first complete JSON object from `text`.

    The Gonka judge emits its object twice, concatenated
    (PR #309 quirk, part of the instrument per preregistration
    S2): only the first complete object is read. Raises
    ValueError when no complete object exists.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in judge output")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object in judge output")


def parse_judge_output(text: str) -> dict:
    """Validate a judge v3 verdict. Fail-closed: anything that
    is not {accept: bool, score: number in [0,100], reasons}
    raises ValueError, which the caller records as an error row
    (an unscored row is never a silent zero)."""
    obj = first_json_object(text)
    accept = obj.get("accept")
    score = obj.get("score")
    if not isinstance(accept, bool):
        raise ValueError("judge accept missing or not boolean")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("judge score missing or not numeric")
    if not 0.0 <= float(score) <= 100.0:
        raise ValueError("judge score out of range")
    if "reasons" not in obj:
        raise ValueError("judge reasons missing")
    return {"accept": accept, "score": float(score),
            "reasons": obj["reasons"]}


JUDGE_TEMPLATE = (
    'Judge the candidate answer to this task. Reply with one '
    'JSON object: {"accept": bool, "score": 0-100, '
    '"reasons": str}. Accept only if the answer satisfies '
    'every stated constraint.\n\nTask: ')


def adapt_candidate(row: dict) -> dict:
    """Adapt a frozen successor-corpus row ({id, instruction,
    kind, task_kind}) to the package candidate shape. The
    task_shape of a probe episode is NOT a corpus field: it is
    assigned at pattern-freeze time by the distiller pass (see
    the freeze record), so it is deliberately absent here."""
    prompt = row["instruction"]
    return {"id": row["id"], "task_kind": row["task_kind"],
            "prompt": prompt,
            "judge_prompt": JUDGE_TEMPLATE + prompt}


# ------------------------------------------------------------------
# Calibration wave (preregistration S3)
# ------------------------------------------------------------------

def screen_candidate(transport: Transport, candidate: dict) -> dict:
    """Screening (ratified amendment, 2026-11-18): the candidate
    is first ANSWERED by its kind's proposer organ (S2 roles);
    the judge then scores (task + answer) twice. Screening an
    unanswered task is meaningless - a judge with no answer can
    only score 0, which would fill the probe set with garbage;
    the successor instrument this package inherits screened
    answered episodes. The validator is NOT part of screening:
    screening's currency is judge scores, the validator enters
    at arm episodes, where accept is the currency. Membership
    is by the mean, the A/B spread is recorded first-class
    (S3 variance rule). Any organ failure raises
    (stop-on-first-error)."""
    roles = ORGAN_ROLES[candidate["task_kind"]]
    p_provider, p_model = roles["proposer"]
    answer = transport(p_provider, p_model, candidate["prompt"], 1024)
    prompt = (candidate["judge_prompt"]
              + "\n\nCandidate answer:\n" + answer)
    provider, model = JUDGE_ORGAN
    a = parse_judge_output(transport(provider, model, prompt, 1024))
    b = parse_judge_output(transport(provider, model, prompt, 1024))
    mean = (a["score"] + b["score"]) / 2.0
    return {"id": candidate["id"], "task_kind": candidate["task_kind"],
            "score_a": a["score"], "score_b": b["score"],
            "mean": mean, "spread": abs(a["score"] - b["score"]),
            "spread_flag": abs(a["score"] - b["score"]) > SPREAD_FLAG,
            "brain_proposer": f"{p_provider}/{p_model}",
            "brain_judge": f"{provider}/{model}",
            "answer": answer}


MAX_CALIB_CONCURRENCY = 4


class ScreeningError(RuntimeError):
    """Stop-on-first-error, global across the calibration pool:
    the first judge failure stops new candidate launches;
    candidates already in flight finish and their rows are
    carried here as `completed` so the caller can keep them,
    while the failed row goes to the phase's invalid file
    (preregistration S7 quarantine discipline)."""

    def __init__(self, failed_id: str, cause: Exception,
                 completed: list[dict]):
        super().__init__(f"screening stopped at {failed_id}: {cause}")
        self.failed_id = failed_id
        self.cause = cause
        self.completed = completed


def screen_pool(candidates: list[dict], judge: Transport,
                max_workers: int = MAX_CALIB_CONCURRENCY
                ) -> list[dict]:
    """Screen candidates with bounded concurrency (hub tempo
    amendment, 2026-11-18). Screening is per-candidate
    independent - no shared state - so concurrency changes
    nothing about any candidate's condition; result order is
    the candidate order, never the completion order. The arms
    are NOT screened here and stay sequential."""
    completed: dict[int, dict] = {}
    in_flight: dict = {}
    idx = 0
    error: tuple[str, Exception] | None = None

    def submit_next(ex) -> None:
        nonlocal idx
        if idx < len(candidates):
            fut = ex.submit(screen_candidate, judge, candidates[idx])
            in_flight[fut] = idx
            idx += 1

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for _ in range(min(max_workers, len(candidates))):
            submit_next(ex)
        while in_flight:
            done, _ = wait(list(in_flight),
                           return_when=FIRST_COMPLETED)
            for fut in done:
                i = in_flight.pop(fut)
                exc = fut.exception()
                if exc is None:
                    completed[i] = fut.result()
                elif error is None:
                    error = (candidates[i]["id"], exc)
            if error is None:
                for _ in range(len(done)):
                    submit_next(ex)
            # on error: launch nothing new; the loop drains
            # what is already in flight into `completed`.
    if error is not None:
        raise ScreeningError(
            error[0], error[1],
            [completed[i] for i in sorted(completed)])
    return [completed[i] for i in sorted(completed)]


def calibrate(candidates: list[dict], judge: Transport) -> dict:
    """Screen the pool and select the probe set.

    Band rule (mechanical, one-shot, S3): screen under
    DEFAULT_BAND; if members < MIN_PROBE or the in-band fraction
    exceeds 70% (band not discriminating), re-derive the band
    ONCE as [median-15, median+15] of the screened means and
    re-select from the SAME runs (no new judge calls). If the
    probe set is still short, the package verdict is
    INSTRUMEN_TIDAK_CUKUP - reported, never patched around.
    """
    if len(candidates) > SCREEN_BUDGET_FROZEN:
        raise ValueError("frozen pool exceeds the screening budget")
    screened = screen_pool(candidates, judge)
    means = [s["mean"] for s in screened]

    def select(band):
        return [s for s in screened if band[0] <= s["mean"] <= band[1]]

    band = DEFAULT_BAND
    members = select(band)
    rederived = False
    if len(members) < MIN_PROBE or (
            screened and len(members) / len(screened) > 0.70):
        med = statistics.median(means)
        band = (med - 15.0, med + 15.0)
        members = select(band)
        rederived = True
    language = [m for m in members if m["task_kind"] == "language"]
    return {
        "band": list(band), "band_rederived": rederived,
        "screened": screened, "probe_set": members,
        "probe_n": len(members),
        "language_n": len(language),
        "scope": "mixed" if len(language) >= MIN_LANGUAGE
                 else "code-only",
        "sufficient": len(members) >= MIN_PROBE,
        "verdict_if_stopped_here": None if len(members) >= MIN_PROBE
                                   else "INSTRUMEN_TIDAK_CUKUP",
    }


# ------------------------------------------------------------------
# Arms (preregistration S5) and verdict (S6)
# ------------------------------------------------------------------

ARMS = ("POLA", "RECEIPT", "SHAM", "KOSONG")


def build_context(arm: str, episode: dict,
                  patterns: list[dict]) -> tuple[str, list[str], bool]:
    """Return (context_text, context_ids, delivered).

    POLA recalls distilled patterns by task_shape equality (the
    design #254 vocabulary match - there is no similarity
    threshold). Delivered is False when a context arm has
    nothing to deliver; that is a datum, not an error (the
    EVO 0005 lesson). KOSONG is delivered by definition.
    """
    if arm == "KOSONG":
        return "", [], True
    if arm == "POLA":
        hits = [p for p in patterns
                if p["task_shape"] == episode.get("task_shape")]
        if not hits:
            return "", [], False
        text = "\n".join(
            f"approach: {p['approach']}\npitfalls: "
            + "; ".join(p["pitfalls"]) for p in hits)
        return text, [p["source_episode"] for p in hits], True
    if arm == "RECEIPT":
        text = episode.get("receipt_text", "")
        return text, [episode["id"]], bool(text)
    if arm == "SHAM":
        text = episode.get("sham_text", "")
        return text, [episode["id"]], bool(text)
    raise ValueError(f"unknown arm {arm!r}")


def run_episode(arm: str, episode: dict, patterns: list[dict],
                transport: Transport) -> dict:
    """One episode under one arm: proposer -> validator -> judge.

    The episode accept (verdict currency, S6) is the judge's
    accept on the validated proposal; a validator rejection
    closes the episode as not accepted without spending a judge
    call (recorded as judge_skipped). A judge failure raises
    (stop-on-first-error)."""
    context, context_ids, delivered = build_context(arm, episode,
                                                    patterns)
    roles = ORGAN_ROLES[episode["task_kind"]]
    p_provider, p_model = roles["proposer"]
    v_provider, v_model = roles["validator"]
    prompt = episode["prompt"]
    if context:
        prompt = f"{context}\n\n{prompt}"
    proposal = transport(p_provider, p_model, prompt, 1024)
    validation = transport(
        v_provider, v_model,
        "Validate this proposal for the task. Reply RATIFY or "
        f"REJECT with one line of reason.\n\nTask: "
        f"{episode['prompt']}\n\nProposal: {proposal}", 256)
    ratified = validation.strip().upper().startswith("RATIFY")
    row = {"episode_id": episode["id"], "arm": arm,
           "task_kind": episode["task_kind"],
           "context_ids": context_ids, "delivered": delivered,
           "brain_proposer": f"{p_provider}/{p_model}",
           "brain_validator": f"{v_provider}/{v_model}",
           "validator_ratified": ratified}
    if not ratified:
        row.update({"accepted": False, "score": None,
                    "judge_skipped": "validator_rejected"})
        return row
    j_provider, j_model = JUDGE_ORGAN
    verdict = parse_judge_output(transport(
        j_provider, j_model,
        "Judge this episode. Reply with one JSON object: "
        '{"accept": bool, "score": 0-100, "reasons": str}.\n\n'
        f"Task: {episode['prompt']}\n\nProposal: {proposal}", 512))
    row.update({"accepted": verdict["accept"],
                "score": verdict["score"],
                "brain_judge": f"{j_provider}/{j_model}"})
    return row


def run_arm(arm: str, probe_set: list[dict], episodes: dict,
            patterns: list[dict], transport: Transport,
            seed: int) -> list[dict]:
    """Run one arm over the probe set in a seeded shuffled
    order (the seed is recorded by the caller)."""
    order = list(probe_set)
    random.Random(seed).shuffle(order)
    return [run_episode(arm, episodes[m["id"]], patterns, transport)
            for m in order]


def compute_verdict(arm_rows: dict[str, list[dict]],
                    probe_set: list[dict]) -> dict:
    """Delivery gate + verdict rule (S6), with the dual
    variance report: the sensitivity readout excludes episodes
    whose calibration spread exceeded SPREAD_FLAG and never
    changes the primary verdict."""
    flagged = {m["id"] for m in probe_set if m["spread_flag"]}

    def readout(rows_by_arm, exclude: set):
        rates, gates = {}, {}
        for arm, rows in rows_by_arm.items():
            kept = [r for r in rows if r["episode_id"] not in exclude]
            delivered = [r for r in kept if r["delivered"]]
            gates[arm] = (len(delivered) / len(kept)
                          if kept else 0.0)
            rates[arm] = (
                sum(1 for r in delivered if r["accepted"])
                / len(delivered) if delivered else 0.0)
        return rates, gates

    rates, gates = readout(arm_rows, set())
    sens_rates, _ = readout(arm_rows, flagged)
    if any(g < DELIVERY_GATE for g in gates.values()):
        verdict = "TIDAK_TERANTAR"
    elif rates["POLA"] > rates["RECEIPT"] and rates["POLA"] > rates["KOSONG"]:
        verdict = "TERDUKUNG"
    else:
        verdict = "NOL"
    # Hub ratification condition (2026-11-18): judge_skipped
    # counts per arm are a required consolidation readout.
    skipped = {arm: sum(1 for r in rows if r.get("judge_skipped"))
               for arm, rows in arm_rows.items()}
    return {"verdict": verdict, "accept_rates": rates,
            "delivery_rates": gates,
            "sensitivity_accept_rates": sens_rates,
            "judge_skipped_per_arm": skipped,
            "flagged_episodes": sorted(flagged)}


# ------------------------------------------------------------------
# Transport binding: the vault-connector helper scripts
# ------------------------------------------------------------------

HELPER_DIRS = Path.home() / "workspace" / "custom-connectors"


def helper_transport(provider: str, model: str, prompt: str,
                     max_tokens: int) -> str:
    """Call one registered organ through its connector helper
    (`<provider>_call.py chatfile <model> <file> <max_tokens>`)
    and return the completion text. Credentials stay in the
    vault: the helper's surrogate flow handles them."""
    helper = (HELPER_DIRS / f"custom.{provider}" / "bin"
              / f"{provider}_call.py")
    with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False,
            encoding="utf-8") as fh:
        fh.write(prompt)
        prompt_file = fh.name
    try:
        out = subprocess.run(
            ["python3", str(helper), "chatfile", model,
             prompt_file, str(max_tokens)],
            capture_output=True, text=True, timeout=600)
    finally:
        Path(prompt_file).unlink(missing_ok=True)
    if out.returncode != 0:
        raise RuntimeError(
            f"{provider} helper failed: {out.stderr.strip()[:300]}")
    result = json.loads(out.stdout)
    if isinstance(result.get("content"), str):
        # Flattened envelope (groq / gemini / cloudflare helpers).
        return result["content"]
    return result["choices"][0]["message"]["content"]
