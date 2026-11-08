# ACE R9 (Gemini Lane) — Independent Recovery & Methodological Audit (2026-11-07)

**Audited branch:** `research/gemini-r9-representation-transfer`
**Base `main` SHA:** `80104ce50ecbcea21080bed8c0eabce88d47ccb5`
**Pre-registration commit:** `3d4be019708b4efcfd720179b6cd2f50dfe0f1b5` (`docs/ACE_R9_GEMINI_PRESCORE.md` only)
**Implementation & results commit:** `5e708634be446011596f197d0e899e85c7f3581b`
**Recovered patch:** `/home/antigravity/ACE_R9_Gemini_commits.patch` (`139,165` bytes, SHA-256 `977ffc41eb7476e00e94b7b5bbed2477a68d1427ee09eea1849631497813b4bb`)
**Scientific status:** `NOT_ASSESSED` | **Release status:** `BLOCK_RELEASE` | **OAIE:** `NOT_ESTABLISHED`

---

## 1. Recovery & Multi-Version SHA-256 Verification

1. **Commit Ordering & Provenance**:
   - `3d4be01` touches **only** `docs/ACE_R9_GEMINI_PRESCORE.md` (`167` lines, zero `.py` files, zero scored results).
   - `5e70863` adds `code/ace_research_reptransfer/*` (`10` modules), `docs/ACE_R9_GEMINI_RESULTS.md`, `evidence/reptransfer/r9_gemini_v1.json.gz`, and `.github/workflows/ace-gemini-r9.yml`.
   - `tools/verify_sources.py`: `PASS` (`25/25` pinned upstream files untouched; pure Python standard library, zero external packages).
2. **Cross-Version Bitwise Reproducibility**:
   - Uncompressed `evidence/reptransfer/r9_gemini_v1.json.gz` (`509,759` bytes) SHA-256:
     `1f8f5836b79a811c6413879823ca6f21f6def998b4944d72f46f6bd697412d91`
   - Independent fresh replays via `PYTHONPATH=code python -m ace_research_reptransfer.runner` and `ace_research_reptransfer.verify` produced the **exact same SHA-256** (`1f8f5836b79a811c6413879823ca6f21f6def998b4944d72f46f6bd697412d91`) across **Python 3.11.2, Python 3.12.16, and Python 3.13.18**.
3. **Verified Primary Numbers (`B = 32`)**:
   - `U` mean `M`: **A = `0.9805`**, A0 = `0.0680`, B (fresh R1) = `0.0169`, **C = `0.1068`**, **C2 = `0.9656`**, D0 = `0.0000`.
   - `L` mean `M`: **A = `0.9911`**, **C = `0.9911`**, C2 = `0.9911` (zero regression).
   - `N` false admissions (`B = 32`): `0` across all arms (`A`, `A0`, `B`, `C`, `C2`, `D0`).
   - `H6` semantic drift (`B = 32`): **FAIL** (`A = 9/10` false admissions with terminal accuracy `< 0.10`; `C2 = 9/10`; `C = 5/10`; `OPEN_WORLD_SAFETY = FAIL`).

---

## 2. Methodological & Code Audit Findings (Strengths & Weaknesses)

### 2.1 Confirmed Strengths
- **Strict Terminal Non-Leakage**: AST audit (`audit_diagnostics.check_ast_import_isolation`) and adversarial label-flipping unit test (`TestAdversarialNonLeakage`) confirm no fit module (`tasks.py`, `sampling.py`, `features.py`, `head.py`, `arms.py`) ever imports `evaluator.py` or reads terminal strings/labels.
- **Causal Source Specificity (`A` vs `A0`)**: Same R1 learner + same 26-feature dictionary size + same pair-adapter achieves `0.9805` from relevant sources (`S_rel`) vs `0.0680` from irrelevant sources (`S_irr`), proving the gain comes from transferred DFA state structure rather than adapter capacity alone.

### 2.2 Audited Weaknesses & Scope Limits
1. **Researcher Co-Design of `S_rel` Relative to `C` vs `C2`**:
   - Base library `C` (`r1.fixed_predicates()`, `100` features) includes `mod 2` and `mod 3` symbol counters (`count_mod`), omitting `mod 4`, whereas all 6 `U` targets use `ca%4` or `cb%4` supplied via `S_rel`.
   - Against the informed hand library `C2` (`148` features including `mod 2..6`), `A` ties ungated accuracy (`0.9805` vs `0.9656`, mean regret `-0.0148`). Thus `A`'s real advantage over `C2` is **hypothesis-space compactness**:
     - Candidate hypotheses evaluated per unit: `A = 352` vs `C2 = 11,026` (~31.3× fewer).
     - Fit symbol reads per `U` unit at `B=32`: `A = 55,296` (+ `15,127` amortized source pretraining = `70,423`) vs `C2 = 1,729,668` (~24.6×–31.3× lower).
2. **Source Regime Horizon Ceiling (`mod >= 5` and 3-gram suffix)**:
   - Exhaustive length `0..5` R1 induction fails source admission (`6..12`) on `ca%5==0` (`2,010/8,128` errors) and `ends:abb` (`113/8,128` errors).
3. **Prescore Items Omitted from Primary `runner.py` Summary (Remediated in `audit_diagnostics.py`)**:
   - **Secondary Agreement-Gate (`A_g, A0_g, C_g, C2_g`)**: `probe_strings(seed)` was defined in `sampling.py` (`ACE_R9_GEMINI_PRESCORE.md` §4) but not wired into `runner.py`. Executing `audit_diagnostics.py` shows an important compactness effect: at `B=32` on `U`, `A_g` achieves **`0.8315`** (`coverage 0.8333`) vs `C2_g` **`0.6831`** (`coverage 0.7000`), and at `B=16` on `N`, `A_g` has **`0` false admissions** vs `2` for `C_g`/`C2_g`, because `C2`'s larger `11,026`-hypothesis pool suffers higher version-space disagreement.
   - **Explicit `transfer_regret` (`ACE_R9_GEMINI_PRESCORE.md` §6)**: Computed in `audit_diagnostics.py` (`U_b32` mean regret vs blind `max(B, C)` = `-0.8737`; vs non-blind `max(B, C, C2)` = `-0.0148`).
   - **Minor R1 cost-formula discrepancy**: `ACE_R9_GEMINI_PRESCORE.md` §6 specified `merge_attempts × Σ(len+1)` while `arms.py:82` recorded `attempts * Σ(len)` (off by `+1` state-entry step per training string; does not affect any accuracy, admission, or hypothesis gate).
4. **Information-Theoretic Unidentifiability of `H6` Semantic Drift**:
   - Under `H6` (`D1`, `D2`), train (`0..5`) and validation (`6..12`) labels are generated from the nominal rule while terminal (`16..30`) truth is complemented.
   - Even with unlabeled probe agreement gating (`A_g`), once `B=64` pins down the unique nominal hypothesis (`exact_survivors = 1`), `A_g` commits **`10/10` false accepts**. Two worlds with identical observational distributions over all accessible inputs are **mathematically indistinguishable** without interventional terminal queries or side-channel provenance; ACE must never claim passive detection of unobservable semantic inversion.
