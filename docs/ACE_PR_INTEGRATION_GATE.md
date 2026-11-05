# ACE PR Integration Preflight

Owner: coordinator integration lane. Independent of core engineering, receipt reliability, CI regression, and frozen E1.4 research.

This tool is read-only. It makes only GitHub API GET calls and does not merge, write, deploy, or change any science result. The output is a path-level coordination gate, NOT a proof of semantic compatibility, CI success, ancestor commit integrity, or scientific improvement.

## Reproduce

Run tests from the repository root:

    python -m unittest discover -s tools -p 'test_ace_pr_collision_gate.py' -v

Live snapshot (requires a GitHub token with repository read permission):

    GITHUB_TOKEN=... python tools/ace_pr_collision_gate.py --repo dianzherdiana25-hash/ACE

Scoped, historical two-PR snapshot (no network):

    python tools/ace_pr_collision_gate.py --repo dianzherdiana25-hash/ACE --snapshot evidence/coordination/pr26_pr27_snapshot_20261105.json

Exit codes: 0 means no same-base file-path collision (cross-stack matches still require review); 2 means BLOCK_INTEGRATION for sibling PRs touching the same path; 1 means UNKNOWN_INCOMPLETE_EVIDENCE due to malformed/incomplete data, pagination limit, network error, or rate limit. The command writes deterministic JSON with canonical snapshot SHA256.

## Verified current collision (2026-11-05)

- PR #26, HEAD aba67d6c7572550b84ff464eba850cf2b6fdccc7, and PR #27, HEAD 965640786cbf2f8adcd89eb1d980945f78c2da77.
- Both PR bases are research/e15-autonomous-research-loop.
- Both change code/ace_loop/source_evolution.py and code/ace_loop/test_source_evolution.py.
- Offline two-PR preflight result: BLOCK_INTEGRATION, blocking_overlap_count=1, exit code=2.
- This snapshot is intentionally scoped to two PRs and does not assert that other open PRs have been scanned by the recorded offline command.

On the observed exact HEAD, GitHub Actions run #42032051955 (PR #26) concluded failure; run #42033475872 (PR #27) concluded success on 46 targeted tests, not full repository regression. This gate does not certify CI conclusions or independently explain the failing run. The CI lane owns failure diagnosis.

## Integration policy

Before considering either branch for integration, obtain fresh PR metadata, all changed-file pages, exact SHA CI and semantic review. Resolve the sibling overlap through an explicitly reviewed integration candidate or select one variant; do not blindly merge source_evolution.py from both.

Do not edit frozen E1.4 locks or overturn scientific HOLD/NOT_ASSESSED. This PR itself introduces no branch protection, workflow, or mandatory merge restriction; its BLOCK status is an advisory review gate until it is integrated into policy or CI.

Path-based overlaps in transitive stacked PRs are suppressed when base ref matches another active PR head. Matches on unrelated base refs produce MANUAL_REVIEW_REQUIRED. A branch outside the open-PR set cannot be assumed as a known dependency. Avoid claiming scientific advancement from this tooling alone.
