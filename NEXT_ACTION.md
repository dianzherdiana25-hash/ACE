# Aksi berikutnya untuk Work, Codex, atau chat ini

**Last accepted checkpoint:** E1.4c-v1 HOLD with shared-PRNG flaw at bf43a97, E1.4c-v2 corrected frozen at caedbe7 and scored HOLD. [v2 report](design/e1.4/E14C_V2_POOL_INDEPENDENCE_RESULT_v1.md), [raw evidence](evidence/e14/e14c_v2_public_development_v1.json). Do not use a positive pooled mean to overrule the prespecified four-stratum decision.

1. Design E1.4d to learn **when** to reuse an acquired question-selection policy based on task-level features and uncertainty, rather than inheriting one static family heuristic. Do not tune on the v1/v2 target outcomes.
2. Build new independent source/target motifs and new query pools, with target-hidden generator and oracle separation, plus controls: local max-partition, random single label, no-label, sham, and strong grammar-informed baseline. Include no-disagreement, both-wrong, negative transfer and representation-insufficient cases.
3. Account for total source acquisition + target label costs and CPU, not only one-label target-arm parity. Predeclare paired family/regime acceptance criteria before scoring; keep failures and raw denominators.
4. Restore genuine isolated evaluator using official Bubblewrap if possible and test nonexposure of evaluator data, worker environment and network. A same-process module split is not independent custody.
5. Run bounded stages with heartbeat and terminal state, commit tested evidence on research/e1.3-design, read back HEAD. No additional costs, no sealed E1.3 confirmation, no Tod/main changes.
