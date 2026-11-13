
## PROGRAM KECEPATAN — addendum (owner order, 2026-11-13 21:20 WIB)

"ajukan teknis yang bisa lebih cepat, lebih masif,
dalam pengembangan" — a named speed offensive on
every MEASURED bottleneck. Per-item state:

1. **SERVING — low-thread config ADOPTED NOW.**
   All A3B work in the sandbox home runs `-t 1`
   (flash-attn indifferent, default KV) from the
   collected evidence: screening tg 2.52–2.56 and
   confirmation -r 3 tg 2.46 ± 0.10 vs the recorded
   -t 8 baseline tg 0.91 (≈2.7–2.8×); KV q4_0
   rejected (worse both axes). Recorded in the
   arena record (evidence/bakeoff_arena30b_benchmark
   .json, `serving_config_adoption`). NO A3B run at
   -t 8 in this home from now on.
2. **SERVING NEXT — ngram speculative decoding**
   (candidate #5a: no new model, byte-identical
   output protocol, adoption bar tg ≥ 1.25×)
   replaces the stopped tuning grid as the next
   serving test. Owner: the serving lane
   (ik_llama.cpp intake → ngram test).
3. **INTAKE ACCELERATED — ik_llama.cpp** rises from
   waiting to ACTIVE intake: pin commit + tarball
   sha256 through the same custody gate, before/
   after measurement, adopt only at tg ≥ 1.30× with
   no pp regression. Owner: the serving lane (its
   build was already visible in the sandbox on
   2026-11-13 ~22:20 WIB); Ian integrates the
   hub-verified result.
4. **EXPERIMENT RUNS — parallelize + checkpoint.**
   Independent arms/tasks run concurrently in the
   sandbox (8 real cores) when the design allows,
   and the concurrency is RECORDED in the run's
   evidence. Per-task checkpoints in every driver
   (the pattern that saved Stage 0). The adopted
   per-task recording milestone (PR #181) is part
   of this program: it kills future replay costs.
5. **DECISION TIME BOX.** Every ecosystem adoption
   gate gets ONE measuring session per candidate,
   maximum: adopt or reject inside it. Anything
   hanging longer drops class from queue item to
   note. Decision speed is speed too.
