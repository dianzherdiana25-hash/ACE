# Serving lane status — 2026-11-13 ~22:52 WIB
- Intake ik_llama.cpp @7aa7e01: ACCEPTED (sha256 local==sandbox 405b6c45...)
- Build: DONE in sandbox /workspace/tools/ik-llama/src/build/bin/{llama-bench,llama-cli}
- Tainted first run (full house, earlyoom episode): ik plain pp512=13.06 (1.64x baseline, despite contention), tg128=0.42 INVALID (memory crisis)
- ik -rtr + b12316 control in same script: killed mid-load by earlyoom, no numbers
- Blocker: house MemAvailable ~2.3GB with one A3B resident; any 2nd A3B load triggers earlyoom kill of largest RSS. Proposer lane chaining A3B rounds.
- Asked hub for a named ~25-min exclusive RAM window; scripts ready (ik_bench_clean.sh, spec_b12316.sh)
- Deltas sent to hub: #1 intake (d87664d9), #2 build+blocker (8483d5c5)

## Update 23:12 WIB — window #1 invaded via SSH door
- Proposer series ALL_DONE 23:08:02; clean check 23:09:44 (MemAvail 19.7G); launched window sequence 23:09:50.
- 23:10:58 via Tailscale SSH (uid ubuntu): llama-server A3B :18081 launched (proposer_sim/server.log) — same work, other door.
- 23:11:15 earlyoom SIGTERM killed control bench (VmRSS 13,777 MiB, avail 4.82%) rc=143, no numbers.
- Aborted ik_plain myself to protect their server. Server :18081 alive (14.2G RSS).
- Delta #3 to hub (57a91ee9): request re-issued window covering ALL doors or explicit all-clear.

## Update 23:17 WIB — signal issued but server respawned
- Hub signal "RUMAH KOSONG SEMUA PINTU" received 23:16:32; launched 23:16:39.
- BUT: new A3B llama-server :18081 PID 112292 started 23:16:33 (RSS 17.5G) — proposer's server RESPAWNED after their empty confirmation.
- Killed my control bench (112343) + script (112338) within seconds; server unharmed.
- Delta #4 to hub (366f51cb): need respawn source disabled + stability-proven empty before re-signal.
