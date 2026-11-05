# E1.4q — pre-score query interface and hypothesis discrimination

E1.4o's original graph-chain label is binary and often arrived after the third purchased label. E1.4p introduced a minimum-cost evaluator over multiple paths. This experiment isolates the effect of using that richer interface to design one discriminating query.

Freeze 12 fresh public blocks, six with a shared three-event prefix and six with distinct prefixes. Each block supplies four fixed seven-event hypotheses and eight private probe graphs. Each probe admits exactly one of the hypotheses. Evaluate all four possible truths as paired worlds per block. The block is the independent unit. The given version spaces isolate query design and are not learned in this experiment.

Every arm may score at most eight offers and purchase at most one oracle label. Chain constructs one eight-edge path from each candidate. Packed constructs up to three exact paths sharing the prefix, with distinct positive tolls, and two-path graphs with separate interiors when prefixes differ. Random constructs three-path graphs with uniformly sampled distinct tails, independent of candidate words. All offers obey 16 nodes, forward edges, and the same graph contract. Route length is eight edges. Rank every arm by the number of singleton response buckets, then by the sum of squared bucket sizes and proposal order. Buy nothing if no offered graph separates candidates. Apply the observed cost to filter the supplied hypotheses and report only unanimous probe outputs.

**Packed GO** requires full correct coverage for all four truth worlds in at least 5/6 shared-prefix blocks and strictly more shared-prefix full worlds than chain and random. Keep mixed-prefix results, total labels, nodes, edges, errors and abstentions. A gain from a richer oracle interface does not upgrade E1.4o's chain gate or prove autonomous representation invention. NATURAL_HOLD remains separate.

Freeze bank, worker and audit before scoring. The worker receives only candidate words, a mode and a seed. Keep targets and probes outside the worker. Run bounded isolated score, fresh replay, and independent oracle audit.
