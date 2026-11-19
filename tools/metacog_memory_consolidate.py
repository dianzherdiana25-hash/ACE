#!/usr/bin/env python3
"""C3 — Konsolidasi Memori Metakognitif (Lapis 3, strictly read-only).

Membaca snapshot memori/audit secara baca-saja (``memory.jsonl`` berantai hash,
``checkpoints/self_dev/metacognitive_memory.json``, maupun snapshot JSONL episode)
untuk mengelompokkan kegagalan/keberhasilan berulang, risiko negative transfer,
temuan HIGH terbuka, dan celah kalibrasi — lalu memancarkan ringkasan
metakognitif deterministik tanpa pernah menulis ke memory store hidup.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


SCHEMA = "ace.metacog-consolidation.v1"

_STOP_TOKENS = frozenset(
    {
        "the", "and", "for", "with", "from", "into", "that", "this", "was", "were",
        "dan", "yang", "pada", "dari", "untuk", "dengan", "saat", "atau", "ke",
        "di", "oleh", "adalah", "tidak", "gagal", "sukses", "pass", "fail", "failed",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _rel_or_posix(path: Path, root: Path) -> str:
    try:
        return PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _normalize_mode_token(text: str) -> str:
    cleaned = re.sub(r"\b[0-9a-f]{8,}\b", "", text.lower())
    cleaned = re.sub(r"\b\d+\b", "", cleaned)
    cleaned = re.sub(r"[^a-z_]+", "_", cleaned).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned or "unspecified_mode"


def _signature_stem(summary: str) -> str:
    # Normalkan token angka/ID agar pola kegagalan yang berulang menggumpal rapi
    s = summary.lower().replace("_", " ")
    s = re.sub(r"\b[0-9a-f]{7,}\b", " ", s)
    skip = _STOP_TOKENS | {"cand", "hyp", "ep", "run", "rcpt", "mem", "task", "autonomous", "paradigm", "shift"}
    tokens = [
        t
        for t in re.findall(r"[a-z]{3,}", s)
        if t not in skip and not re.fullmatch(r"(?:ord|seq|v|c|g|j)\d*", t)
    ]
    if not tokens:
        return "general"
    return "_".join(tokens[:4])


def _is_failure_record(raw: dict[str, Any]) -> bool | None:
    if "actual_success" in raw and isinstance(raw["actual_success"], bool):
        return not raw["actual_success"]
    if "actual_failure" in raw and isinstance(raw["actual_failure"], bool):
        return raw["actual_failure"]
    if "success" in raw and isinstance(raw["success"], bool):
        return not raw["success"]
    status = str(raw.get("status") or raw.get("verdict") or "").strip().upper()
    if status in {"FAIL", "FAILED", "ERROR", "GAGAL", "NOT_DEMONSTRATED", "NO-GO", "REJECTED", "HOLD"}:
        return True
    if status in {"PASS", "PASSED", "OK", "SUCCESS", "DEMONSTRATED", "LIFT_DEMONSTRATED", "ADOPTED"}:
        return False
    cls = str(raw.get("class") or (raw.get("content") or {}).get("class") or "").strip().lower()
    if cls in {"finding_high_opened", "failure", "regression"}:
        return True
    if cls in {"skill_verified", "finding_high_closed", "verdict_sealed", "mission_ratified"}:
        return False
    return None


def _parse_memory_jsonl_readonly(
    target: Path,
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ekstrak observasi episode, temuan HIGH, superseded, dan negative transfer baca-saja."""
    rel = _rel_or_posix(target, root)
    sha = _sha256_file(target)
    raw_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()

    observations: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    records_by_id: dict[str, dict[str, Any]] = {}
    tombstones = 0
    saw_event_log = False

    for line_no, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            malformed.append({"path": rel, "line": line_no, "error": str(exc)})
            continue
        if not isinstance(obj, dict):
            malformed.append({"path": rel, "line": line_no, "error": "line is not a JSON object"})
            continue

        if "event" in obj and isinstance(obj.get("event"), dict):
            saw_event_log = True
            ev = obj["event"]
            etype = ev.get("type")
            if etype == "record" and isinstance(ev.get("record"), dict):
                rec = dict(ev["record"])
                rec["_line"] = line_no
                records_by_id[str(rec.get("id") or f"line_{line_no}")] = rec
            elif etype == "supersede":
                rid = str(ev.get("record_id") or "")
                if rid in records_by_id:
                    records_by_id[rid]["status"] = "superseded"
                    records_by_id[rid]["superseded_by"] = ev.get("by")
            elif etype == "outcome":
                rid = str(ev.get("record_id") or "")
                if rid in records_by_id:
                    outcomes = dict(records_by_id[rid].get("outcomes") or {})
                    ctx = str(ev.get("context") or "default")
                    bucket = dict(outcomes.get(ctx) or {"success": 0, "fail": 0})
                    key = "success" if ev.get("success") else "fail"
                    bucket[key] = int(bucket.get(key, 0)) + 1
                    outcomes[ctx] = bucket
                    records_by_id[rid]["outcomes"] = outcomes
            elif etype == "tombstone":
                rid = str(ev.get("record_id") or "")
                records_by_id.pop(rid, None)
                tombstones += 1
            continue

        # Flat JSONL snapshot record
        is_fail = _is_failure_record(obj)
        content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
        summary = str(
            obj.get("summary")
            or content.get("event")
            or content.get("text")
            or obj.get("error")
            or obj.get("reason")
            or _canonical_json(content or obj)
        )
        domain = str(
            obj.get("task_family")
            or obj.get("family_tag")
            or obj.get("domain")
            or content.get("subject")
            or obj.get("kind")
            or "general"
        )
        mode = str(obj.get("failure_mode") or obj.get("error_type") or content.get("class") or "")
        if not mode:
            mode = _signature_stem(summary) if is_fail else "verified_outcome"
        pred_p = obj.get("predicted_prob")
        observations.append(
            {
                "record_id": str(obj.get("episode_id") or obj.get("id") or f"line_{line_no}"),
                "outcome_kind": "failure" if is_fail else ("success" if is_fail is False else "neutral"),
                "domain": _normalize_mode_token(domain),
                "mode": _normalize_mode_token(mode),
                "context": str(obj.get("context") or "default"),
                "summary": summary,
                "predicted_prob": float(pred_p) if isinstance(pred_p, (int, float)) and not isinstance(pred_p, bool) else None,
                "source_kind": str((obj.get("source") or {}).get("kind") or obj.get("source_kind") or "snapshot"),
                "pointer": {"path": rel, "sha256": sha, "line": line_no, "record_id": str(obj.get("episode_id") or obj.get("id") or f"line_{line_no}")},
            }
        )

    neg_transfers: list[dict[str, Any]] = []
    superseded_records: list[dict[str, Any]] = []
    opened_findings: dict[str, dict[str, Any]] = {}
    closed_findings: set[str] = set()

    if saw_event_log:
        for rec in sorted(records_by_id.values(), key=lambda r: (int(r.get("written_seq") or 0), str(r.get("id") or ""))):
            rid = str(rec.get("id") or "")
            content = rec.get("content") if isinstance(rec.get("content"), dict) else {}
            summary = str(content.get("event") or content.get("text") or content.get("name") or content.get("task") or _canonical_json(content))
            cls = str(content.get("class") or "").strip().lower()
            domain = str(content.get("subject") or content.get("task_family") or content.get("family_tag") or rec.get("kind") or "memory")

            if rec.get("status") == "superseded":
                superseded_records.append(
                    {
                        "record_id": rid,
                        "superseded_by": rec.get("superseded_by"),
                        "summary": summary,
                        "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                    }
                )

            finding_key = str(content.get("finding_id") or content.get("subject") or "")
            if not finding_key and cls in {"finding_high_opened", "finding_high_closed"}:
                m = re.search(r":\s*([A-Za-z0-9_.-]+)$", summary)
                finding_key = m.group(1) if m else _signature_stem(summary)
            if cls == "finding_high_opened":
                opened_findings[finding_key] = {
                    "finding_key": finding_key,
                    "record_id": rid,
                    "summary": summary,
                    "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                }
            elif cls == "finding_high_closed":
                closed_findings.add(finding_key)

            outcomes = rec.get("outcomes") or {}
            if rec.get("kind") == "procedural" and isinstance(outcomes, dict) and outcomes:
                contexts_with_success = [c for c, v in outcomes.items() if int(v.get("success", 0)) > 0]
                for ctx, counts in sorted(outcomes.items()):
                    succ_n = int(counts.get("success", 0))
                    fail_n = int(counts.get("fail", 0))
                    for _ in range(fail_n):
                        observations.append(
                            {
                                "record_id": f"{rid}:{ctx}:fail",
                                "outcome_kind": "failure",
                                "domain": _normalize_mode_token(domain),
                                "mode": _normalize_mode_token(f"procedural_fail_{summary}"),
                                "context": str(ctx),
                                "summary": f"{summary} (context={ctx})",
                                "predicted_prob": None,
                                "source_kind": str((rec.get("source") or {}).get("kind") or "evidence"),
                                "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                            }
                        )
                    for _ in range(succ_n):
                        observations.append(
                            {
                                "record_id": f"{rid}:{ctx}:succ",
                                "outcome_kind": "success",
                                "domain": _normalize_mode_token(domain),
                                "mode": _normalize_mode_token(f"procedural_pass_{summary}"),
                                "context": str(ctx),
                                "summary": f"{summary} (context={ctx})",
                                "predicted_prob": None,
                                "source_kind": str((rec.get("source") or {}).get("kind") or "evidence"),
                                "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                            }
                        )
                    if fail_n > succ_n or (succ_n == 0 and any(c != ctx for c in contexts_with_success)):
                        neg_transfers.append(
                            {
                                "record_id": rid,
                                "summary": summary,
                                "failing_context": ctx,
                                "context_success": succ_n,
                                "context_fail": fail_n,
                                "succeeded_elsewhere": [c for c in contexts_with_success if c != ctx],
                                "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                            }
                        )
            else:
                is_fail = _is_failure_record(
                    {
                        "class": cls,
                        "status": content.get("status") or content.get("verdict"),
                        "failure_mode": content.get("failure_mode"),
                        "actual_success": content.get("actual_success"),
                    }
                )
                if is_fail is True:
                    mode = str(content.get("failure_mode") or cls or _signature_stem(summary))
                    observations.append(
                        {
                            "record_id": rid,
                            "outcome_kind": "failure",
                            "domain": _normalize_mode_token(domain),
                            "mode": _normalize_mode_token(mode),
                            "context": str(content.get("context") or "memory"),
                            "summary": summary,
                            "predicted_prob": None,
                            "source_kind": str((rec.get("source") or {}).get("kind") or "evidence"),
                            "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                        }
                    )
                elif is_fail is False:
                    mode = str(cls or "verified_skill_or_verdict")
                    observations.append(
                        {
                            "record_id": rid,
                            "outcome_kind": "success",
                            "domain": _normalize_mode_token(domain),
                            "mode": _normalize_mode_token(mode),
                            "context": str(content.get("context") or "memory"),
                            "summary": summary,
                            "predicted_prob": None,
                            "source_kind": str((rec.get("source") or {}).get("kind") or "evidence"),
                            "pointer": {"path": rel, "sha256": sha, "line": rec.get("_line"), "record_id": rid},
                        }
                    )

    open_high = [v for k, v in sorted(opened_findings.items()) if k not in closed_findings]
    meta = {
        "negative_transfer_alerts": neg_transfers,
        "superseded_debt": superseded_records,
        "open_high_findings": open_high,
        "tombstone_count": tombstones,
        "malformed_lines": malformed,
    }
    return observations, meta


def _parse_metacog_json_readonly(target: Path, root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rel = _rel_or_posix(target, root)
    sha = _sha256_file(target)
    try:
        data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return [], [{"path": rel, "line": 1, "error": str(exc)}]

    observations: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("history"), dict):
        for cand_id, entry in sorted(data["history"].items()):
            if not isinstance(entry, dict):
                continue
            actual_fail = bool(entry.get("actual_failure"))
            pred_p = entry.get("predicted_prob")
            stem = _signature_stem(cand_id)
            observations.append(
                {
                    "record_id": str(cand_id),
                    "outcome_kind": "failure" if actual_fail else "success",
                    "domain": "self_dev_hypothesis",
                    "mode": _normalize_mode_token(stem),
                    "context": "self_dev",
                    "summary": str(cand_id),
                    "predicted_prob": float(pred_p) if isinstance(pred_p, (int, float)) else None,
                    "source_kind": "metacognitive_checkpoint",
                    "pointer": {"path": rel, "sha256": sha, "record_id": str(cand_id)},
                }
            )
    elif isinstance(data, dict) and isinstance(data.get("records"), list):
        for idx, row in enumerate(data["records"], start=1):
            if not isinstance(row, dict):
                continue
            is_fail = _is_failure_record(row)
            if is_fail is None:
                continue
            summary = str(row.get("summary") or row.get("id") or f"rec_{idx}")
            observations.append(
                {
                    "record_id": str(row.get("id") or f"rec_{idx}"),
                    "outcome_kind": "failure" if is_fail else "success",
                    "domain": _normalize_mode_token(str(row.get("task_family") or row.get("kind") or "general")),
                    "mode": _normalize_mode_token(str(row.get("failure_mode") or _signature_stem(summary))),
                    "context": str(row.get("context") or "default"),
                    "summary": summary,
                    "predicted_prob": float(row["predicted_prob"]) if isinstance(row.get("predicted_prob"), (int, float)) else None,
                    "source_kind": "json_records",
                    "pointer": {"path": rel, "sha256": sha, "record_id": str(row.get("id") or f"rec_{idx}")},
                }
            )
    return observations, []


def _cluster_observations(
    observations: list[dict[str, Any]],
    outcome_filter: str,
    *,
    min_cluster_size: int,
    overconfident_threshold: float,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        if obs["outcome_kind"] != outcome_filter:
            continue
        grouped[(obs["domain"], obs["mode"])].append(obs)

    clusters: list[dict[str, Any]] = []
    for (domain, mode), items in grouped.items():
        cluster_key = f"{domain}::{mode}"
        cid = "mcl_" + hashlib.sha256(f"{outcome_filter}:{cluster_key}".encode("utf-8")).hexdigest()[:12]
        probs = [i["predicted_prob"] for i in items if i["predicted_prob"] is not None]
        y_succ = 0.0 if outcome_filter == "failure" else 1.0
        cal: dict[str, Any] | None = None
        if probs:
            mean_p = sum(probs) / len(probs)
            mae = sum(abs(p - y_succ) for p in probs) / len(probs)
            overconf = (
                sum(1 for p in probs if p >= overconfident_threshold)
                if outcome_filter == "failure"
                else 0
            )
            cal = {
                "samples_with_prob": len(probs),
                "mean_predicted_prob": round(mean_p, 6),
                "empirical_success_rate": y_succ,
                "mean_abs_calibration_error": round(mae, 6),
                "overconfident_failures": overconf,
            }
        pointers = [i["pointer"] for i in items]
        clusters.append(
            {
                "cluster_id": cid,
                "outcome_kind": outcome_filter,
                "cluster_key": cluster_key,
                "domain": domain,
                "mode": mode,
                "count": len(items),
                "recurring": len(items) >= min_cluster_size,
                "contexts": sorted({i["context"] for i in items}),
                "sample_summaries": sorted({i["summary"] for i in items})[:3],
                "record_ids": [i["record_id"] for i in items],
                "calibration": cal,
                "source_pointers": pointers,
            }
        )

    clusters.sort(key=lambda c: (-c["count"], c["cluster_key"], c["cluster_id"]))
    return clusters


def consolidate_metacognitive_memory(
    inputs: list[str | Path],
    *,
    root: str | Path = ".",
    min_cluster_size: int = 2,
    overconfident_threshold: float = 0.70,
) -> dict[str, Any]:
    """Konsolidasikan snapshot memori dan audit kegagalan/keberhasilan secara read-only."""
    repo_root = Path(root).resolve()
    observations: list[dict[str, Any]] = []
    negative_transfers: list[dict[str, Any]] = []
    superseded_debt: list[dict[str, Any]] = []
    open_high_findings: list[dict[str, Any]] = []
    malformed_lines: list[dict[str, Any]] = []
    tombstones_total = 0
    files_scanned: list[dict[str, Any]] = []
    missing_inputs: list[str] = []

    for raw_in in inputs:
        p = Path(raw_in).resolve()
        if p.is_dir():
            cand = p / "memory.jsonl"
            if not cand.is_file():
                missing_inputs.append(_rel_or_posix(p, repo_root))
                continue
            p = cand
        elif not p.is_file():
            missing_inputs.append(_rel_or_posix(p, repo_root))
            continue

        rel = _rel_or_posix(p, repo_root)
        files_scanned.append({"path": rel, "sha256": _sha256_file(p)})

        if p.suffix.lower() == ".json":
            obs, mal = _parse_metacog_json_readonly(p, repo_root)
            observations.extend(obs)
            malformed_lines.extend(mal)
        else:
            obs, meta = _parse_memory_jsonl_readonly(p, repo_root)
            observations.extend(obs)
            negative_transfers.extend(meta["negative_transfer_alerts"])
            superseded_debt.extend(meta["superseded_debt"])
            open_high_findings.extend(meta["open_high_findings"])
            malformed_lines.extend(meta["malformed_lines"])
            tombstones_total += int(meta["tombstone_count"])

    failure_clusters = _cluster_observations(
        observations,
        "failure",
        min_cluster_size=min_cluster_size,
        overconfident_threshold=overconfident_threshold,
    )
    success_clusters = _cluster_observations(
        observations,
        "success",
        min_cluster_size=min_cluster_size,
        overconfident_threshold=overconfident_threshold,
    )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "min_cluster_size": min_cluster_size,
        "files_scanned": files_scanned,
        "missing_inputs": missing_inputs,
        "totals": {
            "observations": len(observations),
            "failures": sum(1 for o in observations if o["outcome_kind"] == "failure"),
            "successes": sum(1 for o in observations if o["outcome_kind"] == "success"),
            "failure_clusters": len(failure_clusters),
            "recurring_failure_clusters": sum(1 for c in failure_clusters if c["recurring"]),
            "success_clusters": len(success_clusters),
            "negative_transfer_alerts": len(negative_transfers),
            "open_high_findings": len(open_high_findings),
            "superseded_debt": len(superseded_debt),
            "tombstones_observed": tombstones_total,
            "skipped_malformed": len(malformed_lines),
        },
        "failure_clusters": failure_clusters,
        "success_clusters": success_clusters,
        "negative_transfer_alerts": negative_transfers,
        "open_high_findings": open_high_findings,
        "superseded_debt": superseded_debt,
        "skipped_malformed": malformed_lines,
    }


def render_markdown(report: dict[str, Any]) -> str:
    t = report["totals"]
    lines = [
        "# Konsolidasi Memori Metakognitif ACE (C3)",
        "",
        f"- **Skema**: `{report['schema']}` (`read_only={report['read_only']}`)",
        f"- **Berkas dipindai**: {len(report['files_scanned'])} | **Observasi**: {t['observations']} "
        f"(kegagalan={t['failures']}, keberhasilan={t['successes']})",
        f"- **Kluster kegagalan**: {t['failure_clusters']} (berulang >= {report['min_cluster_size']}: {t['recurring_failure_clusters']})",
        f"- **Peringatan negative transfer**: {t['negative_transfer_alerts']} | **Temuan HIGH terbuka**: {t['open_high_findings']}",
        "",
        "## Kluster Kegagalan",
        "",
    ]
    if not report["failure_clusters"]:
        lines.append("- _(Tidak ada kluster kegagalan.)_")
    else:
        for c in report["failure_clusters"]:
            tag = "BERULANG" if c["recurring"] else "TUNGGAL"
            cal_txt = ""
            if c["calibration"]:
                cal_txt = f" | MAE={c['calibration']['mean_abs_calibration_error']}"
            lines.append(
                f"- **[{tag}] `{c['cluster_id']}` (`{c['cluster_key']}`)**: {c['count']} kejadian, "
                f"konteks={c['contexts']}{cal_txt} — contoh: `{c['sample_summaries'][0]}`"
            )
    lines.extend(["", "## Kluster Keberhasilan", ""])
    if not report["success_clusters"]:
        lines.append("- _(Tidak ada kluster keberhasilan.)_")
    else:
        for c in report["success_clusters"]:
            lines.append(
                f"- **`{c['cluster_id']}` (`{c['cluster_key']}`)**: {c['count']} kejadian, konteks={c['contexts']}"
            )
    if report["negative_transfer_alerts"]:
        lines.extend(["", "## Peringatan Negative Transfer", ""])
        for n in report["negative_transfer_alerts"]:
            lines.append(
                f"- `{n['record_id']}` gagal di `{n['failing_context']}` "
                f"(fail={n['context_fail']}, succ={n['context_success']}; berhasil di={n['succeeded_elsewhere']})"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Akar repositori")
    parser.add_argument("--input", dest="inputs", action="append", required=True, help="Berkas/direktori snapshot memori atau log episode JSONL/JSON")
    parser.add_argument("--min-cluster-size", type=int, default=2)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = consolidate_metacognitive_memory(
        args.inputs,
        root=args.root,
        min_cluster_size=args.min_cluster_size,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
