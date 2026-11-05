# ACE E1.4u source + evidence handoff

This ZIP contains an exploratory E1.4u two-path graph representation study. Integrate files into a clean ACE checkout at PR #15 HEAD e1ff5537986d9f9563fcabcb236a2956e4cfe511, or review standalone. None of the frozen E1.4t protocol, bank or scores is modified.

Read docs/ACE_E14U_DEVELOPMENT_v0.md and design/e1.4/E14U_PROTOCOL_DEV_v0.md first. Full code and test sources are in code/e14; original 168-arm JSON (in-process and worker isolated), seed sensitivity and 130-test log are under WORK.

## Scientific interpretation

130/130 Python tests pass on the locally reconstructed partial E1.4t workspace, not the full repository. 42 worlds x 4 strategies were executed both in process and across 404 isolated worker process launches; 168/168 deterministic arm outcomes matched. 236 paid labels were replay-audited. A new researcher-authored branch-pair graph predicate achieves 28/28 exact recovery in its own assisted synthetic development set but has no independently demonstrated open-ended primitive invention or OAIE. The accepted scientific status remains HOLD / NOT_ASSESSED.

## Reproduce

See commands inside docs/ACE_E14U_DEVELOPMENT_v0.md. A working Linux unshare/chroot namespace sandbox is required for the isolated run; successful canaries are not certified native Bubblewrap equivalence.
