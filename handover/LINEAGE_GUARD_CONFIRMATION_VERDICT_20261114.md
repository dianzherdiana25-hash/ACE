# PROGRAM VERDICT — LINEAGE-GUARD CONFIRMATION RUN: GUARD_ADOPTED (2026-11-14)

> **Status:** Consolidated verdict of the Lineage-Guard confirmation protocol under [`docs/research/ACE_LINEAGE_GUARD_PREREG_FULL_DRAFT_20261113.md`](../docs/research/ACE_LINEAGE_GUARD_PREREG_FULL_DRAFT_20261113.md) (PR #188), built in [`evidence/lineage_guard_harness.py`](../evidence/lineage_guard_harness.py) & [`evidence/lineage_guard_gate.py`](../evidence/lineage_guard_gate.py) (PR #193), executed in the verified Manus Sandbox R3 custody (`/workspace/ace-custody-lineage-guard`, PR #195 + PR #196) after Stage 3 confirmation of P1+P2+P3 (PR #192, commit `c6d58af7`).

---

## 1. Verdict & Activation Record (§8 + §A.7)

| Field | Value |
|---|---|
| **Mechanical Verdict (§A.7)** | **`GUARD_ADOPTED`** |
| **Trigger Reference (§8.1)** | PR #192 merged on `main` (`c6d58af7f63ad0aef8bb8ad77676e715795ebaa2`) confirming P1+P2+P3 on `20261601–20261603` |
| **Confirmation Band Seeds (§8.2)** | `[20261701, 20261702, 20261703]` (consecutive, disjoint from `20261501–20261503` and `20261601–20261603`) |
| **Registry Snapshot (§8.3)** | `/workspace/ace-custody-lineage-guard/wt-battery/code/ace_operational/distractor_registry.json` (`sha256 f9d8982a1314cc5807f815dc700affd0c3dd9cf42ff2b35855a7704dc0911680`), IDs: `["name-swap-523014-nc-band20261501"]` |
| **Activation Record (§8)** | [`evidence/lineage_guard_state/act_confirm_20261701.json`](../evidence/lineage_guard_state/act_confirm_20261701.json) (`sha256 73ae373fcb68d2ba9d371254bb893fcd1b923211801a4fe4665143f49cb676c9`) |
| **Top Evidence Record** | [`evidence/lineage_guard_run.json`](../evidence/lineage_guard_run.json) (`sha256 49d575a7792c...`, pulled tarball `trackb_results.tar.gz` `sha256 fa558307c5d3163184b6cec18cc6fbbba08dd82aeea17c75803da5029fec579e`) |
| **Window (R3 Empty RAM)** | `2026-11-14` Manus Sandbox `2887726280f4`, zero model processes resident (`21,609 MiB` available RAM) |

---

## 2. Pre-Run Custody & Gate Checks (Steps 1–4)

| Step | Check | Result |
|---|---|---|
| **R3 Custody Baseline (PR #196)** | 80 files / `1,049,673` bytes (`tree_digest = c02221775c2b81117effb93b204cccd0aaaa930e166e4a9c3883cf1d233fc6c2`) | `problems: []`, `extras: []`, `digest_match: true` (**PRISTINE**) |
| **Battery Supplement (PR #195)** | `distractor_inoculation.py` (`cbc5e7df...`) + `distractor_registry.json` (`f9d8982a...`) | `tree_digest = f4d3c43bc86576e9c0eb16b95da7bb1eb42f62805b4733bcf558b1905654c5ef` (**VERIFIED**) |
| **Step 1 — Unit Tests (§B.4)** | `evidence/test_lineage_guard_harness.py` inside custody | **`12/12 PASS`** |
| **Step 2 — L4 Logging Invariance** | `catalog_control-020` & `catalog_control-021` × Arms A/B (`stock == param == guarded_off`) | **`PASS`** (`4/4 identical=True`, Stage 0 hashes exact) |
| **Step 3 — L1/L2 Reproduction** | Dev witnesses (`band 20261501`), Arm B stock (`guard OFF`) | **`PASS`** (`BASE` = 0 from round 2, `death_round = 2`, `true_path = never_generated`) |
| **Step 4 — PR #175 Battery Gate** | `stock` vs `guarded` across 59 admitted keys + `name-swap-523014-nc-band20261501` | `stock = SUSCEPTIBLE`, `guarded = NOT_SUSCEPTIBLE`, `anchor = NO_REGRESSION` (`2/4 -> 4/4`), `l5_violations = 0` (**`GATE PASS`**) |

---

## 3. Confirmation Bands Results (`20261701–20261703`, Steps 5–7)

### Catalog Admission Digests (Step 5)

| Band | Discovery Wall (s) | Admitted Operators / Chains | Catalog SHA-256 Digest | Discovery Snapshot |
|---|---:|---|---|---|
| `20261701` | `1385.05` | `6` keys, `1` chain | `5005072890bf608dc78a98965e6c9a3bf729a517c9689a12a9ccc051cbbaf62a` | [`discovery_20261701.json`](../evidence/lineage_guard_state/discovery_20261701.json) |
| `20261702` | `1149.16` | `6` keys, `0` chains | `465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913` | [`discovery_20261702.json`](../evidence/lineage_guard_state/discovery_20261702.json) |
| `20261703` | `1407.87` | `6` keys, `1` chain | `8113acba7e52eeb1f68189ca03529d8b07ee9d202d21f9bba0c1c9ffffbd95a2` | [`discovery_20261703.json`](../evidence/lineage_guard_state/discovery_20261703.json) |

### Per-Band Cell Matrix (`stock` vs `guarded` × `clean` / `infected`)

| Band | `stock clean` | `guarded clean` | `stock infected` | `guarded infected` | Diverted (`W`) | Recovered (`R`) | Clean Harm (`H`) |
|---|---|---|---|---|---:|---:|---:|
| `20261701` | `34/34` (`373.7s`, `138` calls) | `34/34` (`372.6s`, `138` calls, `0` trig) | **`33/34`** (`425.5s`, `194` calls) | **`34/34`** (`423.7s`, `194` calls, `1` trig) | `1` (`021`) | `1` (`021`) | `0` |
| `20261702` | `34/34` (`326.5s`, `138` calls) | `34/34` (`327.5s`, `138` calls, `0` trig) | **`32/34`** (`324.0s`, `193` calls) | **`34/34`** (`323.0s`, `193` calls, `2` trig) | `2` (`021, 022`) | `2` (`021, 022`) | `0` |
| `20261703` | `34/34` (`370.9s`, `138` calls) | `34/34` (`364.8s`, `138` calls, `0` trig) | **`33/34`** (`353.2s`, `191` calls) | **`34/34`** (`348.4s`, `191` calls, `1` trig) | `1` (`022`) | `1` (`022`) | `0` |
| **Total** | **`102/102`** | **`102/102`** | **`98/102`** | **`102/102`** | **`4`** | **`4` (`100%`)** | **`0`** |

### Mechanical Worksheet & Mechanism Proof (§A.7)

- **Witness class `W` (`|W| = 4`):** `20261701:catalog_control-021`, `20261702:catalog_control-021`, `20261702:catalog_control-022`, `20261703:catalog_control-022`.
- **Recovery class `R` (`|R| = 4`):** Exact recovery on all 4 diverted tasks (**`R = W`**). Each witness under `stock infected` failed in `7` score calls (`death_round = 2`, `true_path = never_generated`, returning distracted hash `6577e3eecf24...`); under `guarded infected`, the guard actuated **once in round 1** (`guard_triggers = 1` on each witness, `0` on every non-diverted task across all `102` clean and `98` unaffected infected tasks) and recovered the exact baseline solution (`6504b23bd0f4...`, `true_path = returned`) in **`7` score calls**.
- **Clean Harm `H` (`|H| = 0`):** Zero regressions across all `102` clean tasks; `guard_triggers = 0` in every `guarded clean` cell.
- **Cost Ratio Over `R`:** `[1.0, 1.0, 1.0, 1.0]` → **`median_cost_ratio = 1.0`** (threshold `<= 3.0`).
- **Death-Round Movement (A.7 Consistency Check):** `death_rounds stock = {2: 4, None: 98}` → `death_rounds guarded = {None: 102}` (zero BASE lineage deaths remain).
- **L5 Actuation Check:** `l5_violations = []` (`0` violations across every guarded solve).

---

## 4. Consolidated PR Lineage & Honest Boundaries

This consolidation integrates and supersedes the four draft PRs in strict custody order:
1. PR #188 (`ACE_LINEAGE_GUARD_PREREG_FRAMEWORK_DRAFT_20261113.md`, `ACE_LINEAGE_GUARD_PREREG_FULL_DRAFT_20261113.md`)
2. PR #195 (`CUSTODY_SUPPLEMENT_MANIFEST_BATTERY_20261114.json`)
3. PR #196 (`CUSTODY_REQUIREMENTS_LINEAGE_GUARD_20261114.md`, `CUSTODY_POPULATION_MANIFEST_20261114.json`, `evidence/r5_custody/`)
4. PR #193 (`evidence/lineage_guard_harness.py`, `evidence/lineage_guard_gate.py`, `evidence/test_lineage_guard_harness.py`, dev-witness baseline `evidence/lineage_guard_state/`)
5. Plus the sealed confirmation run records (`20261701–20261703`) packaged here.

**Honest Boundaries (§A.3 & §A.8):**
- `GUARD_ADOPTED` validates the reserved-slot `BASE`-lineage guard mechanism inside the harness solver ([`solve_task_guarded`](../evidence/lineage_guard_harness.py#L277-L419)) on `control` tasks (`n = 4` diverted witnesses across 3 bands) against distractors whose true path stays in `BASE`; distractors whose winning path lies in `ENRICHED` sit outside `H-LG`.
- Wiring `guard=True` into production/operational solvers (`wt-abcv3` / [`code/ace_operational/operator_discovery.py`](../code/ace_operational/operator_discovery.py)) is the explicit post-verdict engineering step governed by standard PR tests and regression checks.
