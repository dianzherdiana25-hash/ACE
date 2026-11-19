# EVO 0007 — Run Record (execution facts accompanying the consolidation)

Verdict: **TERDUKUNG** (see KONSOLIDASI_EVO_0007.md / consolidation.json).
Rows: 160/160 sealed (40 per arm). Annex frozen sha256:
179bcd2181df080bdaee40177434e84d5014e6e185119c85d86afaa34aa3c9a3

## Brain composition per sealed row (from the rows' own stamps)
Rows alternate by task kind; proposer != validator throughout.
- Code items: proposer groq/qwen/qwen3.8-27b; validator gemini.
- Language items: proposer gemini; validator groq/openai/gpt-oss-120b.
- Rows 1–65: gemini seat = gemini-3-flash-preview (37 code + 28 language).
- Rows 66–160: gemini seat = gemma-4-31b-it (51 code + 44 language),
  per amendment section 10 (language proposer) and section 11
  (flexible validator parser; code validator) of the merged runner
  (PR #313; the shipped runner is byte-identical to the live one).
- Judge (arms phase, uniform across arms): Cloudflare
  llama-3.3-70b-instruct-fp8-fast, after Gonka died mid-calibration
  (401, balance exhausted) — owner contingency ladder.
- Gemini quota ran as a multi-bucket route (3 vault keys, failover on
  quota-class errors only); serving key ledgered per call in
  arms_key_ledger.jsonl.

## Named caveats (part of the result, not footnotes)
- judge_skipped per arm: POLA 20, RECEIPT 28, SHAM 30, KOSONG 31
  (of 40). Accept rates are computed on judged rows; the sensitivity
  rates in consolidation.json are identical to the primary rates.
- Cross-judge limitation: bridge statistic n=12 — band-membership
  agreement 8/12, mean delta -9.58 (range -100..+65). The Gonka and
  Cloudflare judges are NOT interchangeable on language items; no
  cross-phase mean comparison is made.
- Re-screening: selection uses the final-instrument rows
  (screening-semantics amendment); in-band membership shifted between
  passes (cd-code-003 55 / cd-code-011 70 -> cd-code-007 52.5) —
  recorded as measured judge variance on identical conditions.
- Distiller phase history: the first distiller organ was named from
  Groq's PUBLIC catalog (llama-3.3-70b-versatile) and 404'd on this
  account's live 11-model catalog; corrected to openai/gpt-oss-20b,
  error kept on the record (amendment sections 7/9). Final annex is
  single-origin gemini/gemini-3-flash-preview (72 patterns); the 24
  Groq-phase records are archived and excluded (patterns_groq_phase
  stays in the staging custody, not in this folder).

## Run history (19 Nov 2026, WIB)
- Driver died ~13:25 with the VM replacement, at 116/160 rows; the
  gap to the 15:38 relight was the operator's miss, recorded as such.
- Relit resume-safe; the remaining rows crawled through repeated
  Google 503s (capacity errors; zero 429s after relight — not quota).
- Driver retry budget: 10 x 60 s per call (raised during the run;
  named here per the consolidation requirements).
- A detached watcher polled every 90 s, would relight the driver on
  death, and at 160/160 ran the consolidation itself
  (CONSOLIDATION_DONE, 17:30 WIB).
- The remaining KOSONG rows were deliberately finished on the same
  gemma organ rather than swapping models at the finish line, to
  keep the control arm clean; the direction of the result was
  already visible at the 142-row interim (POLA 50% vs KOSONG 14%)
  and the final KOSONG rate settled at 20% (8/40).
