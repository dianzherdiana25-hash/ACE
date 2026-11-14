# SERVING PACKAGE — INTEGRATION REVIEW (2026-11-14)

> Integration of the serving lane's package (ECOSYSTEM INTAKE #01
> candidate #2 ik_llama.cpp and candidate #5a ngram speculative
> decoding, PR #176; speed program addendum 2026-11-13 21:20)
> AS-IS, with firsthand verification by Ian (main execution
> session) at the hub's order, 2026-11-14. The lane was archived
> in the three-chat consolidation (2026-11-14 ~00:20 WIB) with
> its clean bench still unrun. Lane files are reproduced
> byte-identical under `handover/serving-lane/`; the only new
> artifact is this review. Draft PR only, no merge.
>
> Baseline for every comparison below (adopted, PR #176 Wave 1):
> llama.cpp b12316, A3B Q4_K_M, `-t 1`: **pp512 7.96 ± 0.35,
> tg128 2.46 ± 0.10 t/s**.

## 1. Claims verified from the files

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| V1 | **ik_llama.cpp intake passed the custody gate** | VERIFIED as recorded | `serving-lane/evidence/ik_llama_intake_record.json`: pin `ikawrakow/ik_llama.cpp @ 7aa7e01482db892b023bb9aace9a40567ab5297a` (main HEAD at intake, git ls-remote); license MIT verified from the tarball's LICENSE; tarball 35,244,900 B, sha256 `405b6c45219dbe72e174e7e6c8c11a79d4ac917113972cea3c03190d0ebfcb19` computed locally AND in the sandbox — byte-identical (HASH_OK in the build log). `build_ik.sh` enforces the hash fail-closed before extraction (`HASH_MISMATCH_ABORT`). |
| V2 | **Build completed in the sandbox** | VERIFIED as recorded | Lane status 2026-11-13 ~22:52: binaries at `/workspace/tools/ik-llama/src/build/bin/{llama-bench, llama-cli}`; Release, `GGML_NATIVE=ON + AVX512 + AVX512_VNNI`, matched to the host CPU as verified by the lane (Xeon Cascadelake-class: AVX512F/DQ/BW/VL/VNNI present; no VBMI/BF16). Build scripts in this package (`build_ik.sh`, `build2.sh`). The binaries themselves no longer exist — §4. |
| V3 | **Adoption bars, as set** | VERIFIED | Intake record + lane mandate agree: ik adopted iff **tg ≥ 3.198 t/s (1.30× of 2.46) with no pp regression** from 7.96; ngram (candidate #5a, on b12316) adopted iff **generation ≥ 1.25× with byte-identical output** (same prompt+seed, output hash vs the non-speculative arm). |
| V4 | **Bench + ngram protocols are complete and sound** | VERIFIED | `bench_clean.sh`: same-window sequence control b12316 r1 → ik plain r1 → ik `-rtr` r1 (all `-p 512 -n 128 -t 1`), with house-state snapshots (MemAvailable, other model processes) logged before/after every cell — the verdict can be read against the same-window control, not only against the historical baseline. `spec_b12316.sh` / `spec2.sh`: three arms (none / ngram-simple / ngram-mod) on b12316 llama-cli, fixed prompt, `-n 128 -t 1 --seed 42 --temp 0`, per-arm output sha256 — the byte-identity gate is built into the script. |

## 2. What is NOT measured — the bench is VOID, twice

- **U1 — Tainted first run (full house, 2026-11-13 evening).**
  ik plain recorded pp512 **13.06** — the lane and the hub both
  logged this as a SIGNAL only (1.64× baseline pp *despite*
  contention); its tg128 of **0.42 is INVALID** (memory crisis)
  and must never be quoted as a measurement. The ik `-rtr` cell
  and the b12316 control in the same script were killed mid-load
  by earlyoom: no numbers.
- **U2 — Window attempt #1 (launched 23:09:50, after a clean
  check at 23:09:44, MemAvailable 19.7 GB).** At 23:10:58 another
  lane's A3B server arrived through the SSH door; at 23:11:15
  earlyoom killed the control bench mid-load (rc=143). **No
  numbers.** The lane aborted its own ik cell to protect the
  resident server.
- **U3 — Window attempt #2 (hub's all-doors empty sign 23:16:32;
  launched 23:16:39).** An A3B server (started 23:16:33) was
  already loading; the lane killed its own bench within seconds
  to protect it. **No numbers.** (Fault attribution for that
  night was later corrected by the hub — the intruding loads
  were the proposer lane's launches around its corrected run,
  not a respawn mechanism. The serving outcome is unaffected:
  both attempts are VOID.)
- **U4 — Ngram test never ran.** It was queued behind the ik
  bench in the same window sequence; the window never survived
  long enough to reach it. No arm speeds, no identity hashes.

**Net: no adoption verdict is possible for either item.** ik's
tg ratio and pp behaviour at bench conditions are unknown;
ngram's ratio and byte-identity are unknown. The pp signal in
U1 suggests headroom in prompt processing only — it satisfies
no clause of either bar.

## 3. Named deficiencies

- **D1** — No clean tg measurement exists for ik_llama.cpp; the
  only tg figure in the record (0.42) is invalid by the lane's
  own ruling (U1).
- **D2** — The pp 13.06 figure is a contention signal, not a
  bench result; it cannot discharge the "no pp regression"
  clause (D1's sibling).
- **D3** — The hub's window plan includes an r3 confirmation of
  the winning ik cell; `bench_clean.sh` implements the r1 pass
  only. The confirmation is a trivial re-run of the winner at
  `-r 3`, but it is a plan step without a script cell — named
  here so the future runner does not mistake the r1 pass for
  the full protocol.
- **D4** — Sandbox build + all run logs erased by the rollback
  (§4). Restoration is mechanical (pinned tarball, fail-closed
  build script) but the build must be redone before any bench.
- **D5** — The lane's package was never pushed (desk copies
  only, no remote branch) until this PR — storage debt, now
  closed.

## 4. Custody state, verified 2026-11-14 (Ian, D402 door)

- Host 2887726280f4, probed firsthand today:
  `/workspace/tools/ik-llama/` is **ABSENT**; no tool logs
  remain; `/workspace/tools/` holds only `llama.cpp` (the
  b12316 control engine survives). The same rollback that
  erased the lineage-guard custody and the ecosystem intake
  erased this lane's build, tarball, and bench/spec outputs.
- The model survives: `/workspace/ace-omega/models/
  Qwen3-30B-A3B-Q4_K_M.gguf` = 18,556,685,824 B, matching the
  recorded pin size exactly. A re-run therefore needs only:
  tarball re-download (hash-gated by `build_ik.sh`), rebuild,
  and a window — no model intake.

## 5. What an adoption verdict needs, exactly

**ik_llama.cpp:** (a) re-intake + rebuild per V1/V2;
(b) ONE hub-named exclusive RAM window opened by the explicit
all-doors empty sign — the 2026-11-13 lesson, now a standing
rule, is that the sign must cover SSH-door launches and the
empty state must be stability-proven for the window's length;
(c) the `bench_clean.sh` sequence in-window, then the winner's
r3 confirmation (D3); (d) the verdict reads **both** numbers
against V3's bar: tg ≥ 3.198 AND pp no regression vs 7.96,
cross-checked against the same-window control.

**ngram speculative (b12316):** (a) no rebuild needed — the
control engine survives; it can share the ik window or take
its own; (b) the spec script's three arms; (c) the verdict:
generation ratio ≥ 1.25× **AND** output sha256 identical
across arms — any hash mismatch is a REJECT regardless of
speed (V3).

## 6. Package inventory (this PR)

Lane files, byte-identical to the lane desk:
`serving-lane/evidence/ik_llama_intake_record.json`,
`serving-lane/evidence/serving_lane_status.md`,
`serving-lane/scripts/{build_ik.sh, build2.sh, bench_ik.sh,
bench_clean.sh, bench_all.sh, spec_b12316.sh, spec2.sh}`.
(`bench_all.sh` is the earlier combined script from the
tainted run; `bench_clean.sh` is the window protocol of V4.)
New with this review: this document.

— Ian, 2026-11-14. Verification basis: lane package files
as-is; sandbox state probed firsthand via the D402 door
(host 2887726280f4); the night's window history read from
the lane's own status record, with fault attribution as
later corrected by the hub.
