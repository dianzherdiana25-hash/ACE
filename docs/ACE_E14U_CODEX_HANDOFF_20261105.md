# ACE E1.4u — Codex integration handoff (2026-11-05)

**Engineering branch:** `codex/17-e14u-crossgrammar-audit`, based on PR #15 HEAD `cb295d2cf0413f2f1008307ed8d8b72ce3600049`.  
**Task:** https://github.com/dianzherdiana25-hash/ACE/issues/17  
**Parent:** https://github.com/dianzherdiana25-hash/ACE/pull/15  
**Scope:** E1.4u nonconfirmatory engineering development; no scientific GO or OAIE claim.

## Source archive

**Drive:** https://drive.google.com/file/d/1ItJYhmqxrGX9__kbr0nyRVaBUGvWksMV/view

- ZIP `ACE_E14U_Codex_Research_Handoff_v2_20261105.zip`, **39 entries**.
- ZIP SHA-256: `77d6f022d60aa6f8a69d0d3fc802350f04d93b9d0fb53460bfc777ee8e463407`.
- Internal manifest: `MANIFEST_E14U_V2_SHA256.txt`.
- Read archive's `README_E14U_ABLATION_CODEX_HANDOFF.md` first. If the Drive ZIP is not accessible to Codex, the owner may attach it directly to the Codex task.

## Executed local evidence

- Historical partial workspace **130/130 PASS**; new ablation **8/8 PASS**; five algebra tests **5/5 PASS**, each in separate runs (one monolithic 138-test invocation timed out; don't claim it passed).
- Existing E1.4u: 28 two-route pair worlds and four controls: 168 in-process and 168 namespace-worker arms; previous development source is in archive. Historical E1.4t HOLD unchanged.
- New source ablation: **280** in-process arms across 28 prior truth pairs × five source conditions × two policies.
- Original trigger-only incorrectly accepted 10 positive-only, 10 positive-plus-one-negative, and 14 fixed-seed three-random-source worlds. Conservative two-grammar guard: **0 wrong acceptance** on the same 140 arms; 19/28 exact in negative-only, otherwise 28/28.
- **140/140 isolated worker arms matched** in-process on eight deterministic fields across four disjoint 7-world batches: 435 actual namespace worker calls, 295/295 purchased target oracle replays, 308 initial source labels and 840 probe labels; native Bubblewrap certification still missing.
- A separate graph route evaluator agreed on **3,324/3,324** oracle-cost cases.
- Unknown **MIN/SUM** pair cost algebras yielded **21/56 wrong exact acceptances**, disproving universal safety of the two-grammar guard.
- After a *researcher-programmed* three-algebra grammar extension (140 finite candidates), **84/84** MAX/MIN/SUM same-truth worlds recovered exactly with 117 target labels. This is not autonomous operator invention or independent transfer.

## Codex acceptance tasks

1. Compare archive with **fresh** current research/PR heads; integrate non-conflicting new code and tests to this branch with precise SHA and source provenance.
2. Run complete historical+new regression on clean exact-head checkout; save logs and actual test counts and failures.
3. Run real native Bubblewrap or fail **BLOCKED_ENV** with evidence; no silent downgrade to unshare/chroot as an equivalent security boundary.
4. Verify worker target/probe/evaluator nonexposure, per-arm four-label shared cap, replay with *separate* oracle and source/demo/probe accounting; test corrupted receipts.
5. Design a new prespecified, distinct experimental bank with non-target-aware source learning, alternative semantic operators not in the initial grammar, and strong equal-resource baselines. Freeze only **before** viewing target outcomes.
6. Create draft PR to `codex/13-integrated-graph-loop`; **do not merge** without approval; preserve all E1.4t frozen source, score, bank and historical GO/HOLD decisions.

Do not modify Tod, ACE `main`, sealed E1.3 confirmation, or pay for services.
