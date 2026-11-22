"""Ukur variasi prosodi antar-episode dari sampel PCM dan izin analisis yang ditambatkan."""
import argparse
from pathlib import Path
from statistics import median_low
import sys

from ._assets import asset
from ._audio import MAX_WAV
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         identity, integer, obj, read, schema, text)
from .voice_style import analyze


def compare_episodes(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.voice-consistency.v1", ("source_ref", "reference_id", "clips", "limits"))
    source = text(plan["source_ref"], "Pointer kontrak pengukuran")
    reference = identifier(plan["reference_id"], "Episode acuan")
    limits = obj(plan["limits"], ("pitch_delta_hz", "pause_delta_bp", "minimum_windows", "silence_floor"))
    pitch_limit = integer(limits["pitch_delta_hz"], "Selisih pitch", 0, 130)
    pause_limit = integer(limits["pause_delta_bp"], "Selisih jeda", 0, 10000)
    result = {}
    for row in entries(plan["clips"], 16, 2):
        obj(row, ("id", "path", "sha256", "source_ref", "permission_ref"))
        key = identifier(row["id"], "Episode")
        if key in result:
            raise ContractError("ID episode ganda.")
        permission = text(row["permission_ref"], "Izin analisis prosodi")
        raw = asset(root, row["path"], row["sha256"], MAX_WAV)
        policy = {"schema": "ace.media.voice-style-policy.v1", "source_ref": source,
                  "sample_sha256": row["sha256"], "sample_ref": row["source_ref"],
                  "permission": {"purpose": "prosody_reuse", "reference": permission},
                  "minimum_windows": limits["minimum_windows"], "silence_floor": limits["silence_floor"]}
        result[key] = analyze(raw, policy, identity(policy))
    if reference not in result:
        raise ContractError("Acuan episode tidak ada.")
    base = result[reference]
    rows = []
    for key, item in sorted(result.items()):
        reasons = []
        pitch, pause = None, None
        if base["median_pitch_hz"] is None or item["median_pitch_hz"] is None:
            reasons.append("insufficient_voiced_windows")
        else:
            pitch = abs(item["median_pitch_hz"] - base["median_pitch_hz"])
            pause = abs(item["pause_bp"] - base["pause_bp"])
            if pitch > pitch_limit:
                reasons.append("pitch_drift")
            if pause > pause_limit:
                reasons.append("pause_ratio_drift")
        rows.append({"id": key, "sample_sha256": item["sample_sha256"], "source_ref": item["sample_ref"],
                     "pitch_delta_hz": pitch, "pause_delta_bp": pause, "reasons": reasons})
    pitch_changes = [row["pitch_delta_hz"] for row in rows if row["pitch_delta_hz"] is not None and row["id"] != reference]
    return {"schema": "ace.media.voice-consistency-receipt.v1", "plan_sha256": expected,
            "method": "windowed_prosody_measurement", "reference_id": reference, "reference": base,
            "median_episode_pitch_delta_hz": median_low(pitch_changes) if pitch_changes else None,
            "matches": sum(not row["reasons"] for row in rows if row["id"] != reference),
            "status": "hold" if any(row["reasons"] for row in rows) else "consistent_on_measured_features", "episodes": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = compare_episodes(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
