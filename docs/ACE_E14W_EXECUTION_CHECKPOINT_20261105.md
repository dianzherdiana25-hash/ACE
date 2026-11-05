# ACE E1.4w execution checkpoint (2026-11-05)

**Scientific status: PUBLIC DEVELOPMENT / NOT_ASSESSED.**

The E1.4w source, 72 per-batch JSON reports, eight local test-group logs, independent receipt audits, and SHA-256 manifest are preserved in the private project archive:
https://drive.google.com/file/d/1b7GUfhO-DJ9SJBsocLbqJhHXHoTxDnCv/view

Archive SHA-256: `c7d2cef7c059c86bbdea5ae8c79d3d9325a9c5cd9be2a5daece86ca2824de0e1`.
Source bundle JSON: https://drive.google.com/file/d/1vqkaW2sp2PzLYDAFiK0vpko3Rp3kfQSk/view

**Executed in a compatible partial local checkout:** 3,416 arm records (including 768 isolated replays and 56 source-only arms), 384 distinct target-world definitions, 1,931 separate Linux-namespace worker processes, 6,050 purchased target labels across the runs, 386 purchased source labels (including repeated source tasks), and **215/215 local tests PASS in eight bounded commands**.

**Key negative result:** 30 wrong acceptance on the original 192-world fast-acceptance control. The checked policy had 0 there but failed on 10/96 first out-of-grammar worlds and 20/96 further novel out-of-grammar worlds. A postscore near-neighbor canary reduced one error family but failed on a later one; not a general correctness certificate. The source-query policy with 420 candidates solved 18/28 predecessors versus 19/28 from 70 original offers.

Source uses a researcher-authored finite AST grammar of 68 bounded expressions. No autonomous invention of arbitrary semantic operators, no held-out independent science, no native Bubblewrap attestation, and no full exact-head historical repository regression. Historical E1.4t HOLD, E1.4u scientific NOT_ASSESSED and E1.4v NOT_ASSESSED are unchanged.

**Repository integration status (final live readback):** All **13/13** new source/test/protocol/evidence files are committed to PR #19; GitHub live file content was compared byte-for-byte with the archived, locally tested original JSON source bundle and every file matched. The three worker-related files (`code/e14/e14w_worker.py`, `code/e14/e14w_isolated.py`, `code/e14/test_e14w_worker.py`) were temporarily blocked during one tool write attempt but subsequently appeared in the PR head and all three passed exact source readback. Thus earlier incomplete-integration statements are superseded. **Still open:** clean exact-head full historical repository regression, native Bubblewrap worker security attestation, independently preregistered new semantics. Local 215 tests and 768 namespace worker replays are not substitutes for these gates. Draft PR must not be merged as an independently accepted scientific release. Do not modify Tod, ACE main or sealed E1.3 data.
