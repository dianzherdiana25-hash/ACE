# ACE E1.4n — alternative Linux namespace isolation feasibility

**Type:** security-engineering *capability probe*, **not** an E1.4n scoring attempt. **Decision:** `NAMESPACE_FEASIBLE / FROZEN_SCORING_STILL_BLOCKED_ENV`.

On 4 November 2026, a Python 3.13.5 local container successfully executed a new Python worker within real Linux user, mount, network, and PID namespaces, a chroot rootfs with read-only /usr and /solver bind mounts, a private tmpfs /tmp, and a scrubbed environment. The canary exited 0 with all six checks true in ~0.053 seconds. The process was bounded by an 18-second timeout.

[Reproducible standalone probe](../../tools/ace_namespace_capacity_probe.py) · [Captured result](../../evidence/e14/e14n_namespace_capacity_v1.json)

Checks: private host canary file unavailable; evaluator module not mounted; inherited secret env cleared; worker mount read-only; host 127.0.0.1 listener inaccessible from isolated network; host /etc/shadow unavailable.

**What this does not show:** the test uses its own minimal canary worker, not the frozen `e14n_worker.py`. It does not validate the official Bubblewrap binary, E1.4n exact worker invocation, full seccomp/capability policy, cgroup memory or CPU isolation, image provenance, or semantic secrecy across full ACE code. It is not a drop-in Bubblewrap implementation and MUST NOT be passed as `/usr/bin/bwrap` or counted as one of E1.4n's required runtime boundary checks. It also requires Linux namespace and mount permissions that vary by host.

**Remaining blockers:** the session cannot retrieve a complete authenticated private repo checkout directly into the local Python filesystem, and `/usr/bin/bwrap` is absent. The frozen E1.4n manifests and bank remain SHA-256 clean (8/8). Scientific decision remains **PRE-SCORE FROZEN**, not GO/HOLD.

**Next engineering action:** for a future protocol, assess namespace equivalence against the full E1.4g isolation contract under an explicit threat model, add adversarial nonexposure tests using the actual worker/evaluator, check resource bounds, and freeze the new adapter separately before scoring. For **frozen E1.4n**, prefer a host with native official Bubblewrap and complete checkout; run score/replay/audit verbatim with bounded calls and preserve negative findings. Never modify the E1.4n frozen source, data or gate to accommodate the host.

No cost, no changes to Tod/main, and no sealed confirmation data opened.
