# ACE v0.3: counterexample-triggered representation composition

Public synthetic method development. Commit this protocol before implementing
or scoring the new runner. The v0.1/v0.2 and upstream R1/S2 sources stay unchanged.

Question: can a counter hypothesis that falsely accepts observed training words
trigger construction of a product with a learned finite-state guard, using the
unchanged R1 learner and S2 typed counter AST? This is bounded synthesis inside a
human-authored product grammar, not invention of a new primitive type or OAIE.

Learner sees only binary strings and Boolean labels. Training is all 63 strings
of lengths 0 through 5. Enumerate the same seven v0.2 counter slopes. For each,
collect training examples it accepts. Only if these include both positive and
negative labels, and the counter has no training false negatives, train R1 on
that subset. Propose counter AND learned guard; count all merge attempts, AST
node evaluations and predictions. Freeze candidates before validation; select
using validation correctness, then training correctness and canonical identity.
Admission requires exact train and validation fit. Failed fits remain recorded.

Public tasks: equal-counts, equal-counts AND starts-a, equal-counts AND ends-b,
equal-counts AND starts-a AND ends-b, equal-counts AND contains-ab, two-to-one AND
starts-a AND ends-b. Include out-of-class four-to-one and Dyck-prefix balance.
Use fixed task order, three paired seeds (20261106, 20261107, 20261108), 128 unique
balanced validation words at lengths 6 through 12 and 128 unique balanced terminal
words at lengths 16 through 30 per task/seed. Reject duplicate/overlapping inputs;
sampling attempts capped at 100000 per class. Task names/truth functions and
terminal labels are never passed to fitting or selection.

Comparators: unchanged R1 DFA, counter-only search over the same seven slopes,
and a strong fixed-product library of the same counters combined with True,
starts-a, ends-b, starts-a AND ends-b, contains-ab. Fit/select all using the same
train/validation labels. Report actual work separately; these methods are not
compute-matched. A tie with the fixed-product library is explicitly not novelty.

Diagnostics: report terminal accuracy and all failures by task and seed; product
selection on an order-sensitive task must be triggered by actual train errors.
No claimed method advantage unless it beats the fixed-product comparator across
the paired tasks. Preserve a late-rule-inversion witness with identical training
and validation and inverted terminal truth; it cannot be distinguished from the
ordinary task from those observations. Selection must remain identical, and
open-world safety remains false regardless of nominal successes. Keep selected
models immutable and test their fingerprints after later task acquisition.

Require deterministic full-run JSON replay, type/budget validation, independent
semantic evaluation of selected programs, explicit source provenance, and tests
that terminal truth cannot influence model selection. This is PUBLIC_DEVELOPMENT,
scientific NOT_ASSESSED, OAIE not established. Main may host the research library;
merging library code does not deploy any learned candidate or establish safety.
