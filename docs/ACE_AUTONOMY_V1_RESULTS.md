# ACE Durable Autonomous Runtime v1 — Fase 3 Engineering & Verification Report

**Branch:** `engineering/ace-autonomy-v1-20261107` (descended from `d545083a` & PR #67 `d7b311ab`)
**Pre-registration contract:** `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md` (`sha256: b7a540c73fb20df4a6787fccaf48ad409465a411d944ddaa3cc62c28cdaddcbc`)
**Operational evidence:** `evidence/autonomy/autonomy_v1_operational_report.json`
**Scientific status:** `NOT_ASSESSED` | **Release status:** `BLOCK_RELEASE` | **OAIE:** `NOT_ESTABLISHED`

---

## 1. Tiga Status Bukti (Fase 3)

- `ACE_BASE_RUNTIME_EXECUTED`: **`TRUE`** — `ace_runtime` (`931b1582...`) dijalankan langsung maupun melalui `TypedToolBroker` (`ace_demo`, `ace_status`, `ace_enqueue_task`, `ace_run_tasks`, `ace_predict`, `ace_evaluate`, `ace_report`); `tools/verify_sources.py` lulus `25/25`.
- `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED`: **`TRUE`** — seluruh komponen `code/ace_autonomy/` (`Autonomy`, `DeterministicPlanner`, `TypedToolBroker`, `GoalPolicy`, `BudgetController`, `ExternalActionEscrow`, `IndependentVerifier`, `CapabilityRegistry`) berjalan terpadu tanpa intervensi manusia antar-langkah.
- `SCIENTIFIC_CAPABILITY_VALIDATED`: **`FALSE` (`NOT_ASSESSED`)** — `ace_autonomy` adalah fondasi rekayasa ketahanan operasional (Gate 1), bukan klaim keunggulan pembelajaran ilmiah.

---

## 2. Arsitektur Modul & Penyelesaian 12 Gap PR #67 + Red Team RT-01..RT-13

| Komponen | Berkas | Jaminan Rekayasa & Keamanan |
|---|---|---|
| **Exception Hierarchy** | `code/ace_autonomy/errors.py` | `IntegrityError` mewarisi `RuntimeError` (bukan `ValueError`) dan tidak pernah ditelan oleh penangan error langkah operasional. |
| **Execution & Path Policy** | `code/ace_autonomy/policy.py` | Validasi tipe ketat (`type(x) is int/bool` — `RT-11`, `RT-13`), tolak symlink leluhur (`RT-03`), pembacaan file `openat` komponen-demi-komponen dengan `O_NOFOLLOW \| O_NONBLOCK` + `stat.S_ISREG` (menolak FIFO `RT-08` tanpa hang), staging terbatas di `candidates/<goal_id>/`. |
| **Budget Controller** | `code/ace_autonomy/budget.py` | Mengukur dan menegakkan `max_steps` (`<=8`), `max_candidates` (`<=4`), `max_retries_per_step` (`<=1` lokal, `0` eksternal), `wall_seconds` (`time.monotonic`), dan `cpu_seconds` (`RUSAGE_SELF + RUSAGE_CHILDREN` + `RLIMIT_CPU` subproses) → `BUDGET_EXHAUSTED`. |
| **External Action Escrow** | `code/ace_autonomy/escrow.py` | Menyimpan status `DISPATCHED` bertanda tangan HMAC sebelum aksi eksternal dipanggil; jika proses mati (`os._exit`) atau respons ambigu, otomatis beralih ke `HALT_UNCERTAIN` dengan **nol retry otomatis** hingga `reconcile_external()`. |
| **Planner & Goal Manager** | `code/ace_autonomy/planner.py` | Menerjemahkan tujuan bertipe (`inspect_and_verify`, `ace_runtime_demo_and_verify`, `ace_task_learning_cycle`, `stage_candidate_for_review`, `abstain_insufficient_evidence`) menjadi langkah terbatas tervalidasi. |
| **Typed Tool Broker** | `code/ace_autonomy/broker.py` | Menjembatani seluruh siklus `ace_runtime`, inspeksi source aman, suite tes tepercaya dengan `RLIMIT_CPU`, dan staging kandidat tanpa eksekusi (`BLOCKED_ENVIRONMENT_DRAFT_ONLY`). |
| **Independent Verifier** | `code/ace_autonomy/verifier.py` | Memverifikasi pasca-kondisi di disk dan langsung di dalam SQLite `ace_runtime` sehingga bukti palsu (*spoofed receipt*) ditolak *fail-closed* (`IntegrityError`). |
| **Capability Registry** | `code/ace_autonomy/registry.py` | Mencatat kapabilitas operasional & kandidat staging dengan ikatan HMAC terhadap tanda tangan event verifikasi. |
| **Durable Lease Core & Anchor** | `code/ace_autonomy/core.py` | Kunci inisialisasi `fcntl.flock` (`.init.lock`), lease ber-epoch 3-fase tanpa menahan lock selama eksekusi tool, checkpoint per langkah, otomata state ketat (`STAGED_FOR_REVIEW`, `ABSTAINED`, `HALT_UNCERTAIN`, `BUDGET_EXHAUSTED`), serta jangkar monotonik eksternal `.chain_anchor.json` yang menggagalkan pemotongan ekor jurnal (`RT-07`) dan pertukaran DB (`RT-01`). |

---

## 3. Matriks Pengujian Terverifikasi

- **Python 3.12.16**: `20/20` lulus (`ace_autonomy.test_core` `11/11` + `ace_autonomy.test_adversarial_autonomy` `9/9`) + `ace_runtime` `17/17` lulus.
- **Python 3.13.18**: `20/20` lulus (`ace_autonomy.test_core` `11/11` + `ace_autonomy.test_adversarial_autonomy` `9/9`) + `ace_runtime` `17/17` lulus.
- **Source Provenance**: `tools/verify_sources.py` `25/25` cocok dengan blob SHA-1 terpin.
