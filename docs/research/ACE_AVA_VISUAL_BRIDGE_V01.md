# ACE × Autonomous Visual Agent — Evidence-First Bridge v0.1

## Scope and verified boundary

This feature branch adds a small executable, standard-library-only **contract adapter** to ACE. It can plan a single safe edit axis and assess *provided observations* of real returned image assets. It cannot generate, edit, recognize, store or compare photographs on its own. It does not make the ChatGPT image generator an ACE tool, nor confer autonomous computer/browser access. It does not modify the installed Autonomous Visual Agent skill, ACE main, E1.4, or other owners' work.

The source skill inspected for the proposal was Autonomous Visual Agent v0.1.5. Its missing runtime capabilities are not satisfied merely by adding this adapter.

## Desired integration topology

1. **User / host** supplies one original or expressly approved image anchor and a clear change axis. Host enforces legitimate authority, image consent and safety.
2. **AVA planner** creates one editorial single-image request and locks all unrequested axes. Ambiguous 'next' means a small non-intimate micro-detail edit, never progressively more revealing clothing.
3. **Host image tool** runs the approved generation/edit call, if available. This repository package **cannot** call that tool.
4. **Observed-image reviewer** inspects actual returned assets and source for identity consistency, clothing, pose, camera, scene, anatomy and composition; records UNKNOWN when evidence is absent. The local adapter does not infer these observations from text.
5. **ACE-AVA contract gate** rejects unsafe, composite, identity-drifted, unapproved-source and incomplete-evidence results. It emits an auditable JSON receipt.
6. **User** chooses whether to accept any rendition as the next anchor. A generated result is never adopted silently.
7. **ACE research lane (future)** can propose a testable improvement from anonymized metadata, compare to a fixed baseline and maintain failed/negative results. Independent validation remains required before any claimed ability improvement.

The sequence is **plan → external native image execution → original asset inspection → contract review → selection/acceptance**, never 'prompt → imagined score → fake verified image'.

## Runnable local adapter

From ACE repo root:

```sh
PYTHONPATH=code python3 -m unittest discover -s tests -p 'test_ace_visual_bridge*.py' -v
```

Example plan request (metadata only):

```json
{
  "schema": "ace.ava.request.v1",
  "anchor": {
    "asset_id": "user-original-001",
    "provenance": "USER_ORIGINAL",
    "approved_by_user": true,
    "real_or_possible_person": true
  },
  "axis": "camera"
}
```

Save to `/tmp/ava-plan.json`, then run:

```sh
PYTHONPATH=code python3 -m ace_visual_bridge.cli plan < /tmp/ava-plan.json
```

For `review`, append `"expected":5` and `"observations":[...]`. Each observation must have `slot`, `asset_id` (real returned tool ID or null), `image_type` (`SINGLE_PHOTO|COMPOSITE|DOCUMENT|UNKNOWN`), `safety` (`SAFE|BLOCKED|UNKNOWN`), `evidence` (`SOURCE_COMPARE|OBSERVED_IMAGE|UNKNOWN`), `identity` (`MATCH|MISMATCH|UNKNOWN`), `drifted_axes`, `scores` (all six rubric metrics, 0–5), and optional `independently_reviewed` and `accepted_by_user`. Use `UNKNOWN` rather than fictional evidence.

Run `PYTHONPATH=code python3 -m ace_visual_bridge.cli review < /tmp/ava-review.json`.

Important: the CLI trusts the supplied observation fields as metadata; it **does not independently validate** photos, moderation decisions, review independence, user approval or biometrics. Treat it as a transparent contract, not a security boundary against forged observations.

## Measurement and research contract

Rubric weights match AVA's reviewed v0.1.5 skill: identity/reference 35%, wardrobe 25%, pose 15%, camera 10%, anatomy 10%, composition 5%. A tie under 0.10 points requires review. A real-photo edit lacking source comparison is NOT_ASSESSED; no winner may be certified from text scores. Collages do not count as five independently returned photos. A safety refusal blocks that branch; never rephrase and retry to bypass the host.

Acceptance gates:

- **T1**: Five truly separate original photo assets from one authorized task, not five panels. **NOT_ASSESSED here.**
- **T2a/T2b**: Actual files inspected and semantic evaluation supported by visual evidence plus independent human agreement. **NOT_ASSESSED here.**
- **T3**: One authorized correction with native before/after verification. **NOT_ASSESSED here.**
- **T4**: Consented persistent metadata with cross-session readback. **NOT_ASSESSED here.**

Unit tests only establish contract behavior; they do not establish image fidelity or host integration.

## Safe evolution roadmap

**R1 — native test harness:** Capture real returned assets, immutable anchor IDs, requested axis, source/output observations and errors without storing private photos by default; collect user consent before any persistence.

**R2 — evaluator:** Add a separately validated visual comparison provider, calibrated to human judgments, with disagreement adjudication and an UNKNOWN status for ambiguous identities. Avoid unsupported biometric claims.

**R3 — single-image correction:** When an actual result drifts, restart from the last approved original, permit at most one quality-oriented retry per authorized branch, report negative outcomes. Never use repeated attempts to bypass image safety refusals.

**R4 — ACE research:** Use fixed-baseline randomized tasks, separated train/validation/terminal sets, cost-equivalent image calls, negative-control prompts and at least G0→G1→G2 tests. Optimize *editing strategy and observable quality* — not sensitive-content exposure — and only propose plugin release after independent tests.

## Ownership and limitations

Keep this adapter in the isolated research branch until code review. No implicit GitHub merge or release. The installed AVA plugin remains separately managed and requires its exact editable backend source and release ID before an actual plugin update. ACE's execution of this bridge, native image generation, and independent scoring remain unverified until a real host connects them and produces observable evidence.
