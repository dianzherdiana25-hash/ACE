# ECOSYSTEM INTAKE — INTEGRATION REVIEW (2026-11-14)

> Integration of the ecosystem intake lane's package (candidates #3
> lm-evaluation-harness and #4 sqlite-vec of `ECOSYSTEM_INTAKE_01_
> 20261113.md`, PR #176) into the record, AS-IS, with firsthand
> verification by Ian (main execution session) at the hub's order
> (Misi 5, 2026-11-14). The lane itself was archived in the
> three-chat consolidation (2026-11-14 ~00:20 WIB) with its runs
> still queued; this review is the package's closing integration.
> Draft PR only, no merge. Lane files are reproduced byte-identical;
> the only new artifacts are this review and
> `sqlite-vec-trial/baseline_ranks.json`.

## 1. Claims verified from the files

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| V1 | lm_eval × llama.cpp **server path FALSIFIED** at intake | VERIFIED as recorded measurement | Exhibit §"Why the server path is dead" + `intake_manifest.json` `server.backend`: three probes against b12316 llama-server — `logprobs.content` length 1 on a 26-token prompt with `echo=true, logprobs=10` (prompt logprobs do not exist at any `--limit`); the response uses the new OpenAI `content[]` shape, not the legacy `tokens/token_logprobs` shape lm_eval 0.4.13's `gguf`/`local-completions` backends parse; native `/completion` identical. The survey claim in PR #176 candidate #3 does not survive contact with the custodied build. (Probe logs lived in the sandbox intake dir — see §4.) |
| V2 | **llama-perplexity deviation hub-approved** | VERIFIED | Exhibit intake table + manifest `server.replacement_hub_approved`: same b12316 build, `llama-perplexity --multiple-choice` (ARC/HellaSwag) and `--winogrande` (Winogrande); datafiles rendered by `render_tasks.py` from lm_eval 0.4.13's own task definitions over the same pinned datasets; metric labelled **acc_norm analogue** (argmax of mean per-token continuation logprob), NOT raw acc, NOT an lm_eval score. `run_ppl_card.sh` in this package is that runner (the stale server-based `run_card.sh` does not exist in the package). |
| V3 | lm-eval **intake pins complete** | VERIFIED as recorded | `intake_manifest.json`: lm_eval==0.4.13, wheel sha256 `5daaa197…a5286a`, sdist sha256 `f592269f…c967e`, git tag v0.4.13 → commit `ddd67220…0576a0`, dataset revisions (ai2_arc `210d026f…`, hellaswag `218ec52e…`, winogrande `01e74176…`), A3B GGUF sha256 `0d003f66…`, license MIT. `predownload_datasets.py` pins match the manifest exactly. (The in-sandbox `sha256sum -c` pass was the lane's, 2026-11-13; the installed venv no longer exists — §4.) |
| V4 | **Frozen corpus = 12,282 chunks** | VERIFIED firsthand (Ian) | `chunks.jsonl` (lane desk copy): 12,282 lines, 6,909,882 B, **sha256 `97f38dd90ff52a3f6320d79803dd5600428ed38e24e8ad4dcd7d11a90f4d24df`**. Composition resolved byte-exactly: a clean rebuild from origin/main (`git archive` of `08bd8369` + `build_corpus.py`) yields 12,256 chunks / 618 files walked, and every shared path's chunk count is identical; the lane corpus is exactly that **plus 26 chunks from the lane's own 4 in-progress intake files** (the exhibit .md, `predownload_datasets.py`, `render_tasks.py`, `build_corpus.py` — self-inclusion, because the corpus was frozen over the lane's live worktree). "622 files" in the lane's reports = files walked (618 + 4); 615 paths actually contribute chunks. See D5. |
| V5 | **50 hand-labelled queries** | VERIFIED | `queries.jsonl`: 50 lines, `{query, gold}`; gold ids unique, range 0–10,384 ⊂ [0, 12,282) — they index the frozen corpus artifact of V4; ~half the queries are Indonesian-flavoured paraphrases, half English, per the exhibit's description. |
| V6 | **Baseline substring recall@10 = 0.70** | VERIFIED firsthand (Ian) | The package carried this figure as a lane report with no artifact. Ian re-ran trial.py's Arm A logic verbatim (distinct content-words len ≥ 3 as substrings; rank by (score desc, id desc)) over the frozen corpus + queries on 2026-11-14: **recall@10 = 0.70 exactly, 35/50 hits, 15 misses**. Per-query rank table: `sqlite-vec-trial/baseline_ranks.json` (new with this review). |
| V7 | Adoption bar (candidate #4), as written | VERIFIED | PR #176 candidate #4 and `trial.py`'s `bar_met` agree: **Δ recall@10 ≥ +30 points over the substring baseline AND KNN p95 < 50 ms/query at ≥ 10k entries** (corpus is 12,282 — the scale clause is met by construction). |

## 2. The threshold arithmetic (stated, NOT shifted)

Baseline (V6) = 0.70. The bar (V7) demands Δ ≥ +30 points.
0.70 + 0.30 = **1.00**: the sqlite-vec arm passes the recall
clause **only at a perfect 50/50**. Per the hub's standing
instruction this threshold is **not** revised before results
exist; the adoption verdict, when the trial is run, reads the
bar exactly as written. Any revision afterwards is a separate
hub act taken with the full result (both recalls, p95, and the
character of the baseline's 15 misses — now inspectable in
`baseline_ranks.json`) on the table.

## 3. What is NOT measured

- **U1 — Perplexity card numbers: NONE.** The exhibit's results
  table is empty ("—"); there is no `results/` directory in the
  package. Neither the smoke (25/model) nor the full card
  (250 × 2 models) ever ran: the lane's exclusive RAM window was
  third in the night's queue (serving → corrected proposer →
  ecosystem) and never opened before the lane was archived.
- **U2 — sqlite-vec KNN arm: NEVER RUN.** No embeddings cache,
  no trial.db, no results.json exists on the VM or in the
  sandbox. vec recall@10 and KNN p95 latency are both
  unmeasured. `trial.py` + `run_trial.sh` are complete and
  internally consistent; they were simply never executed.

## 4. Custody state, verified 2026-11-14 (Ian, D402 door)

- The sandbox rollback that erased the lineage-guard custody
  (snapshot ≈ 2026-11-13 evening) **also erased this lane's
  entire sandbox-side intake**: `/workspace/tools/` now holds
  only `llama.cpp` (the b12316 build survives). GONE:
  `/workspace/tools/lm-eval-intake/` (venv + pinned datasets +
  probe logs + rendered datafiles), `/workspace/tools/
  sqlite-vec-intake/`, `/workspace/ace-omega/models-embed/`
  (nomic-embed GGUF). Host 2887726280f4, checked firsthand.
- Everything lm-eval-side is **re-derivable from the recorded
  pins** (V3): wheel + sdist hashes, dataset revisions, model
  hash. Restoration is a mechanical re-intake, not research.
- The VM-side package itself was **untracked and unpushed**
  (lane worktree `handover/` was never committed; no remote
  branch existed) until this PR — storage debt, now closed
  for every file except the corpus, which is anchored by its
  sha256 (V4) and retained at `~/workspace/ace-omega/
  lane-intake-eco/chunks.jsonl`. NOTE: the trial must run
  against that artifact hash-checked, NOT against a fresh
  rebuild (a rebuild yields the 12,256-chunk origin/main-only
  corpus — a different frozen set whose ids the gold labels
  do not index).

## 5. Named deficiencies

- **D1** — Card results absent (U1): the exhibit is an intake +
  method record, not yet a comparability exhibit with numbers.
- **D2** — KNN arm unmeasured (U2): candidate #4 has a protocol,
  a frozen corpus, a labelled query set, and a verified
  baseline — and no vec-side number of any kind.
- **D3** — Candidate #2's companion intake is **unpinned in the
  package**: no manifest records the sqlite-vec wheel version/
  hash (0.1.9 per the lane's reports) or the nomic-embed-text-
  v1.5 Q8_0 GGUF hash. `run_trial.sh` assumes both at fixed
  sandbox paths. The pin discipline that V3 shows for lm-eval
  was not replicated for candidate #4 before the lane stopped;
  a fresh intake must record hashes at download time.
- **D4** — Sandbox intake erased by rollback (§4): current
  sandbox state does not match the exhibit's "Installed" row;
  that row is historical (true on 2026-11-13) until a re-intake
  restores it.
- **D5** — Corpus provenance wording: `trial.py`'s docstring
  calls the corpus "chunks of the ACE origin/main tree"; the
  exact composition is origin/main **plus the lane's own 4
  intake files** (V4). Immaterial to the trial's internal
  validity (both arms and all gold labels refer to the same
  frozen artifact), recorded here so no future reader
  "reproduces" the corpus from origin/main alone and silently
  shifts every gold id.

## 6. What an adoption verdict needs, exactly

**Candidate #3 (screening exhibit method):** no threshold is
attached to the card — it is comparability evidence, never
sealed evidence. A verdict ("adopt as ACE's standard external
screening exhibit") needs: (a) re-intake per V3 pins; (b) a
hub-named exclusive RAM window via the SSH door; (c) smoke
25/model with s/item reported, then the full 250 × 2 card;
(d) results + run logs filled into the exhibit table, sanity-
checked against published cards and the frozen chance floors
(ARC 25%, HellaSwag 25%, Winogrande 50%).

**Candidate #4 (sqlite-vec):** a verdict needs: (a) completed
companion intake with hashes recorded (closes D3); (b) one
run of `trial.py --embed` via `run_trial.sh` against the
sha256-checked frozen corpus (V4), producing `results.json`
with vec recall@10 and KNN p95; (c) the bar of V7 applied
**as written** — Δ ≥ +30 points (i.e. vec recall = 1.00
against the verified 0.70 baseline) AND p95 < 50 ms. A vec
recall below 1.00 returns NOT ADOPTED under the bar as
written, whatever the margin; revisiting the bar is a
separate, later hub decision (§2). The embedding load is
small (~0.3 GB); the window/door for the run is the hub's
to name.

## 7. Package inventory (this PR)

Lane files, byte-identical to the lane worktree:
`ECOSYSTEM_LMEVAL_EXHIBIT_01_20261113.md`;
`lm-eval-screening/{intake_manifest.json,
predownload_datasets.py, render_tasks.py, run_ppl_card.sh}`;
`sqlite-vec-trial/{build_corpus.py, trial.py, run_trial.sh,
queries.jsonl}`.
New with this review: `ECOSYSTEM_INTAKE_INTEGRATION_REVIEW_
20261114.md`, `sqlite-vec-trial/baseline_ranks.json`.
Not in the PR (anchored by hash, §4): `chunks.jsonl`
(12,282 chunks, sha256 `97f38dd9…d24df`).

— Ian, 2026-11-14. Verification basis: package files as-is;
corpus + baseline recomputed firsthand on the Muse VM;
sandbox state probed firsthand via the D402 door
(host 2887726280f4).
