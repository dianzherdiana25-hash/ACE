# ACE Research R1 H5 — blind representation selection, null improvement and undetectable drift

**Scientific status: NOT_ASSESSED. H5a: REJECTED. H5b: REJECTED. Overall H5 GO = FALSE.** This is a public, synthetic, researcher-designed experiment only. Do not merge or promote.

## Preregistered provenance

`H5_PROTOCOL.md` was committed at **e53a98a95c1a5e26cebc65f23cdc6fc00086e84a before any H5 implementation or scoring**. No retrospective adjustment to tasks, evaluator budgets, 0.05 accuracy gate, >=16/20 task gate, or >=3/4 drift-abstention gate. Branch `research/chat-r1-primitives`, within `code/ace_research_primitives/` only.

Question: can a controller choose between H1 finite-state induction and H4 counter-register induction from disjoint validation evidence without knowing task names? This is *class selection* within researcher-authored finite/counter model types, **not invention of a new primitive class**. H4 counter construction has pre-existing RPNI fallback; a *fixed always-counter-or-fallback* control is therefore mandatory.

## Exact data and label budget

- 12 fresh seeded synthetic DFA tasks (3 each of nominal source states 2,3,4,5), holdout 256 independently drawn binary strings of lengths 12–18 per task.
- 8 prior H4 counter-language families on new seeded balanced 48-element holdouts; the 2 block tasks additionally use lengths 56–102, exceeding H4.
- 4 deliberate late-drift tasks whose rules are **identical on all train and validation strings** but inverted on length >=8. Their heldout labels are the inversion of base-language labels.
- Per task: 63 fully labeled train strings of lengths 0–5 and 192 paid validation strings of lengths 6–7. Validation labels used only to select between frozen models, never to retrain; holdout is terminal.
- 24 × 63 = **1,512 training labels**; 24 × 192 = **4,608 validation labels**; 12 × 256 + 12 × 48 = **3,648 holdout labels**, **9,768 synthetic oracle labels** total. No paid or external calls.
- Five baseline components: always RPNI, always counter-or-RPNI fallback, best original fixed predicate by train error, suffix3 majority, exact-prefix memorizer. Selected controller uses all 192 validation labels. Tie prefers finite.

## Actual local results

| Family | Tasks | Selector | Always finite | Always counter-or-fallback | Best fixed single predicate |
|---|---:|---:|---:|---:|---:|
| 12 unseen seeded regular DFAs | 12 | **3072/3072 (100%)** | 3072/3072 (100%) | 3072/3072 (100%) | 2460/3072 (80.08%) |
| 8 reused counter families / new holdout | 8 | **384/384 (100%)** | 238/384 (61.98%) | 384/384 (100%) | 192/384 (50%) |
| 4 semantics-switched, train/validation-identical controls | 4 | **0/192 (0%)** | 73/192 (38.02%) | 0/192 (0%) | 96/192 (50%) |

- **H5a REJECTED:** on 20 non-drift tasks, selected mean 100%, best fixed-architecture control mean **100%**, incremental gain **0.00 pp**, below predeclared +5pp. Although 20/20 tasks reached >=90% (>=16 required), the gain gate failed. 12 finite selections; 8 counter selections on non-drift tasks.
- **H5b REJECTED:** no semantic abstention implemented; **0/4** drift tasks flagged, below >=3/4. All four drift tasks earned **0%** holdout accuracy while all training and validation observations were consistent. The four additional choices selected counter, as expected from indistinguishability. The model cannot logically know which matched mechanism is real from its observations.
- **Overall H5 = REJECTED.** This is not negative evidence against all possible primitive induction. It specifically disproves benefit of this validation-based class selector on this bank above the required strong baseline and shows absence of a semantic shift detector.

## Tests, byte provenance and reproducibility

Commands from repo root:
```bash
cd code
PYTHONPATH=. python -m unittest discover -s ace_research_primitives -p 'test_*.py' -q
PYTHONPATH=. python -m unittest ace_research_primitives.test_primitive_discovery ace_research_primitives.test_hard_dfa_study ace_research_primitives.test_h4_counter_induction ace_research_primitives.test_h5_blind_selection -q
PYTHONPATH=. python -m ace_research_primitives.h5_blind_selection --output /tmp/ace-r1-h5.json
PYTHONPATH=. python -m ace_research_primitives.audit_h5 /tmp/ace-r1-h5.json
sha256sum /tmp/ace-r1-h5.json
```

- **51/51 local Python standard-library regression tests PASS** in both discovery and module modes across H1–H5.
- Independent within-team auditor `audit_h5.py` does not call H5 source runner/learner. It reconstructs 12 random DFA sources, all 24 holdouts and labels with its own evaluator; replays saved canonical DFA and counter-register models, checks validation-based selection, all **432 model × split × task scores**, budget and gates. Four H5 test cases reject tampered heldout labels, altered validation selections, corrupted DFA state labels, and forged aggregate GO.
- H5 full raw evidence JSON is **148,163 bytes**, **SHA256 `6aaa5123578f26c20bea24ec0034282becc6069884f49f86734d47ae688b2b08`**. A second independent local generation produced byte-identical SHA256.
- Git object hashes of three tested H5 Python sources **exactly equal GitHub blob SHAs**:
  - `h5_blind_selection.py` = `cf292b0c76dd5ea08539063e18b8734ce2557aa7`;
  - `audit_h5.py` = `00600caaaae239ab46833962f36f2c573390e8d0`;
  - `test_h5_blind_selection.py` = `add48035e1aa49142a16b42830abcc2f4fa2adcd`.

## Failure interpretation and limitations

- The no-improvement H5a result is **not surprising after scoring**: H4 already has an effective rejection-and-fallback strategy which solves both finite and counter families in this bank. Extra validation labels added cost but no gain. A purported “100% success” without this strong baseline would be misleading.
- H5 drift negative controls are intentionally impossible to disambiguate: *all observed training and validation data are identical* to corresponding stable worlds, but holdout semantics diverge. Such controls illustrate nonidentifiability, not a mere programming bug, and force explicit uncertainty disclosure.
- State count 2–5 is an easy regular-language range for H1; counter task templates repeat H4 families. Evaluator and learner were developed within the same team; no independent external test bank. Baselines share labels but not necessarily compute. A holdout picked under a separate research design is required for scientific acceptance.
- All model classes, including counter-register type and fallback, are researcher-authored. **No general new primitive class, cross-task open-ended learning, OAIE, or unconditional semantic guarantee was demonstrated.**

**Release gate:** draft PR only, no merge; exact final GitHub PR-head CI run and independent expert review still OPEN.
