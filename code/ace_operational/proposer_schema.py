"""ACE Omega - proposer engine, Stage 1 (simulation-first).

Schema for a REJECTABLE proposal package ("paket yang dapat ditolak").

Design source: PR #173 section 9 (panen koordinasi #3, "mesin pengusul")
+ PR #177 addendum (PETA ARAH, panen koordinasi #4, item 2/4):
ACE composes a task / catalog-strategy proposal as a package carrying
a claim, a rationale, a cost, and supporting evidence. The package is
submitted for INTERNAL RATIFICATION (ratifikasi internal ACE - hub /
kernel / evidence). It is NOT an owner-approval request; the owner
framing correction (2026-11-13 20:54 WIB) forbids that vocabulary.

Stage 1 is simulation-only: packages are produced and scored against
frozen historical episodes. Nothing in this module dispatches a real
action; there is deliberately no execution path here.
"""

PACKAGE_VERSION = "ace.proposal.v1"

# The exact top-level field set of a package. The validator is
# fail-closed: any missing field, and any unknown field, rejects.
PACKAGE_FIELDS = (
    "package_version",
    "proposal_id",
    "task_kind",
    "claim",
    "rationale",
    "options_considered",
    "recommended_option",
    "cost_estimate",
    "cost_ceiling",
    "evidence",
    "preregistration",
    "risks",
    "uncertainties",
    "stop_controls",
    "ratification",
)

TASK_KINDS = ("task", "catalog_strategy")

COST_FIELDS = ("calls", "wall_seconds", "cost_units")
CEILING_FIELDS = ("max_calls", "max_wall_seconds", "max_cost_units")

STOP_CONTROL_FIELDS = (
    "abort_conditions",
    "sealed_target_status",
    "no_auto_retry",
    "stop_visible",
)

# Vocabulary fence (owner framing correction, 2026-11-13 20:54):
# a package asks for internal ratification, never owner approval.
FORBIDDEN_RATIFICATION_TERMS = (
    "owner_approval",
    "owner_permission",
    "izin_pemilik",
    "persetujuan_pemilik",
)

RATIFICATION_TYPE = "internal_ratification"
RATIFICATION_AUDIENCE = ("hub", "kernel", "evidence")


def empty_package_template():
    """Return the skeleton a proposer must fill; every field required."""
    return {
        "package_version": PACKAGE_VERSION,
        "proposal_id": "",
        "task_kind": "",
        "claim": "",
        "rationale": "",
        "options_considered": [
            {"name": "run", "assessment": ""},
            {"name": "do_not_run", "assessment": ""},
        ],
        "recommended_option": "",
        "cost_estimate": {"calls": 0, "wall_seconds": 0, "cost_units": 0.0},
        "cost_ceiling": {
            "max_calls": 0,
            "max_wall_seconds": 0,
            "max_cost_units": 0.0,
        },
        "evidence": [{"artifact": "", "sha256": ""}],
        "preregistration": {"link": "", "artifact_sha256": ""},
        "risks": [],
        "uncertainties": [],
        "stop_controls": {
            "abort_conditions": [],
            "sealed_target_status": "",
            "no_auto_retry": True,
            "stop_visible": True,
        },
        "ratification": {
            "type": RATIFICATION_TYPE,
            "audience": list(RATIFICATION_AUDIENCE),
        },
    }
