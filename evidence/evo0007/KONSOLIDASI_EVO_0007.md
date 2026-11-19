# KONSOLIDASI EVO 0007

Verdict block: {"verdict": "TERDUKUNG", "accept_rates": {"POLA": 0.5, "RECEIPT": 0.3, "SHAM": 0.25, "KOSONG": 0.2}, "delivery_rates": {"POLA": 1.0, "RECEIPT": 1.0, "SHAM": 1.0, "KOSONG": 1.0}, "sensitivity_accept_rates": {"POLA": 0.5, "RECEIPT": 0.3, "SHAM": 0.25, "KOSONG": 0.2}, "judge_skipped_per_arm": {"POLA": 20, "RECEIPT": 28, "SHAM": 30, "KOSONG": 31}, "flagged_episodes": []}
Rows: 160/160 ({'POLA': 40, 'RECEIPT': 40, 'SHAM': 40, 'KOSONG': 40})
Annex frozen sha256: 179bcd2181df080bdaee40177434e84d5014e6e185119c85d86afaa34aa3c9a3

Execution facts (named, per hub requirements):
- Calibration closed at 54 Gonka-sealed rows; band re-derived [85,115]; probe set 40 (22 code + 18 language), mixed, sufficient.
- Re-screening: selection uses the final-instrument rows (screening-semantics amendment); the in-band membership shift between passes (cd-code-003 55 / cd-code-011 70 -> cd-code-007 52.5) is recorded as measured judge variance on identical conditions.
- Judge amendment: Gonka died mid-calibration (401, balance exhausted); arms judged by Cloudflare llama-3.3-70b-instruct-fp8-fast under the owner contingency ladder, uniformly across arms.
- Bridge statistic (n=12): band-membership agreement 8/12, mean delta -9.58, range -100..+65; the two judges are not interchangeable on language items; no cross-phase mean comparison is made.
- Distiller phase history: sections 7/9 of the amendment record; final annex is single-origin gemini/gemini-3-flash-preview (72 patterns); 24 Groq-phase records archived and excluded.
- Gemini quota became a multi-bucket route (sections 8): three keys, serving key ledgered per call; arms ran as a resume-safe drip with recorded quota pauses.
