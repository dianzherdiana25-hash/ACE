"""Mesin keadaan lapisan proyek (proyek, tonggak, artefak, gerbang verifikasi) (AG80).

Beroperasi murni sebagai pustaka atas ``Protocol`` ``ProjectStore`` tanpa impor
maupun wiring ke ``autonomous_engine``. Memastikan setiap transisi kelulusan
tonggak dan penutupan proyek terhalang fail-closed bila bukti gerbang
verifikasi tidak lengkap atau gagal terverifikasi di store.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Protocol, Sequence


SCHEMA = "ace.project-layer.v1"
MILESTONE_STATES = frozenset({"PENDING", "IN_PROGRESS", "VERIFIED"})
PROJECT_STATES = frozenset({"PLANNED", "ACTIVE", "COMPLETED"})


class ProjectGateError(ValueError):
    """Dilempar bila transisi proyek/tonggak melanggar urutan atau bukti gerbang."""


class ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any] | None: ...
    def save_project(self, project_id: str, data: Mapping[str, Any]) -> None: ...
    def verify_ref(self, ref: str) -> bool: ...


def create_project(
    store: ProjectStore,
    *,
    project_id: str,
    title: str,
    milestones: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Buat proyek baru beserta daftar tonggak terurut dan gerbang wajibnya."""
    pid = str(project_id or "").strip()
    if not pid or not isinstance(title, str) or not title.strip():
        raise ValueError("project_id dan title wajib diisi.")
    if store.get_project(pid) is not None:
        raise ValueError(f"Proyek {pid!r} sudah terdaftar.")
    if not milestones:
        raise ValueError("Proyek wajib memuat minimal satu tonggak.")

    parsed_ms: list[dict[str, Any]] = []
    seen_ms: set[str] = set()
    for idx, m in enumerate(milestones, 1):
        mid = str(m.get("milestone_id") or m.get("id") or f"m{idx}").strip()
        if not mid or mid in seen_ms:
            raise ValueError(f"milestone_id tidak sah atau ganda: {mid!r}")
        seen_ms.add(mid)
        gates = m.get("required_gates") or ["gate_verify"]
        if not isinstance(gates, list) or not gates or not all(
            isinstance(g, str) and g.strip() for g in gates
        ):
            raise ValueError(f"required_gates tonggak {mid!r} wajib daftar tak-kosong.")
        parsed_ms.append(
            {
                "milestone_id": mid,
                "title": str(m.get("title") or mid),
                "status": "PENDING",
                "required_gates": [g.strip() for g in gates],
                "artifacts": [],
                "gate_proofs": {},
            }
        )

    project = {
        "schema": SCHEMA,
        "project_id": pid,
        "title": title.strip(),
        "status": "PLANNED",
        "milestones": parsed_ms,
    }
    store.save_project(pid, deepcopy(project))
    return project


def _find_milestone(project: dict[str, Any], milestone_id: str) -> tuple[int, dict[str, Any]]:
    for idx, ms in enumerate(project["milestones"]):
        if ms["milestone_id"] == milestone_id:
            return idx, ms
    raise ValueError(f"Tonggak {milestone_id!r} tidak ditemukan pada proyek {project['project_id']!r}.")


def register_artifact(
    store: ProjectStore,
    *,
    project_id: str,
    milestone_id: str,
    artifact_id: str,
    ref: str,
    kind: str = "deliverable",
) -> dict[str, Any]:
    """Daftarkan artefak terverifikasi ke salah satu tonggak proyek."""
    proj = store.get_project(project_id)
    if proj is None:
        raise ValueError(f"Proyek {project_id!r} tidak ditemukan.")
    project = deepcopy(proj)
    _, ms = _find_milestone(project, milestone_id)

    aid = str(artifact_id or "").strip()
    ref_s = str(ref or "").strip()
    if not aid or not ref_s:
        raise ValueError("artifact_id dan ref wajib tak-kosong.")
    if store.verify_ref(ref_s) is not True:
        raise ProjectGateError(f"Referensi artefak gagal diverifikasi store: {ref_s!r}")

    ms["artifacts"].append({"artifact_id": aid, "ref": ref_s, "kind": str(kind or "deliverable")})
    store.save_project(project_id, deepcopy(project))
    return project


def start_milestone(
    store: ProjectStore,
    *,
    project_id: str,
    milestone_id: str,
) -> dict[str, Any]:
    """Transisikan tonggak dari PENDING ke IN_PROGRESS setelah tonggak sebelumnya VERIFIED."""
    proj = store.get_project(project_id)
    if proj is None:
        raise ValueError(f"Proyek {project_id!r} tidak ditemukan.")
    project = deepcopy(proj)
    idx, ms = _find_milestone(project, milestone_id)

    if idx > 0 and project["milestones"][idx - 1]["status"] != "VERIFIED":
        raise ProjectGateError(
            f"Tidak dapat memulai {milestone_id!r} sebelum tonggak sebelumnya "
            f"{project['milestones'][idx - 1]['milestone_id']!r} berstatus VERIFIED."
        )
    if ms["status"] == "VERIFIED":
        raise ProjectGateError(f"Tonggak {milestone_id!r} sudah VERIFIED.")

    ms["status"] = "IN_PROGRESS"
    if project["status"] == "PLANNED":
        project["status"] = "ACTIVE"
    store.save_project(project_id, deepcopy(project))
    return project


def verify_milestone_gate(
    store: ProjectStore,
    *,
    project_id: str,
    milestone_id: str,
    gate_evidence: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Verifikasi seluruh gerbang wajib tonggak dan transisikan ke VERIFIED."""
    proj = store.get_project(project_id)
    if proj is None:
        raise ValueError(f"Proyek {project_id!r} tidak ditemukan.")
    project = deepcopy(proj)
    idx, ms = _find_milestone(project, milestone_id)

    if ms["status"] != "IN_PROGRESS":
        raise ProjectGateError(
            f"Tonggak {milestone_id!r} harus IN_PROGRESS sebelum verifikasi gerbang (kini {ms['status']!r})."
        )
    if idx > 0 and project["milestones"][idx - 1]["status"] != "VERIFIED":
        raise ProjectGateError("Tonggak sebelumnya belum VERIFIED.")
    if not isinstance(gate_evidence, Mapping) or not gate_evidence:
        raise ProjectGateError(f"Bukti gerbang verifikasi untuk {milestone_id!r} wajib disediakan.")

    verified_proofs: dict[str, list[str]] = {}
    for gate in ms["required_gates"]:
        refs = gate_evidence.get(gate)
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
            raise ProjectGateError(
                f"Gerbang wajib {gate!r} pada tonggak {milestone_id!r} tidak memiliki bukti."
            )
        checked: list[str] = []
        for raw_ref in refs:
            r = str(raw_ref or "").strip()
            if not r or store.verify_ref(r) is not True:
                raise ProjectGateError(
                    f"Bukti {raw_ref!r} untuk gerbang {gate!r} gagal diverifikasi store."
                )
            checked.append(r)
        verified_proofs[gate] = checked

    if not ms["artifacts"]:
        raise ProjectGateError(
            f"Tonggak {milestone_id!r} belum memiliki artefak terdaftar sebelum verifikasi."
        )

    ms["gate_proofs"] = verified_proofs
    ms["status"] = "VERIFIED"
    store.save_project(project_id, deepcopy(project))
    return project


def complete_project(store: ProjectStore, *, project_id: str) -> dict[str, Any]:
    """Tutup proyek sebagai COMPLETED hanya bila seluruh tonggak sudah VERIFIED."""
    proj = store.get_project(project_id)
    if proj is None:
        raise ValueError(f"Proyek {project_id!r} tidak ditemukan.")
    project = deepcopy(proj)
    unverified = [m["milestone_id"] for m in project["milestones"] if m["status"] != "VERIFIED"]
    if unverified:
        raise ProjectGateError(
            f"Proyek belum dapat ditutup karena tonggak belum VERIFIED: {unverified}"
        )
    project["status"] = "COMPLETED"
    store.save_project(project_id, deepcopy(project))
    return project
