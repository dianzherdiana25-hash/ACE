# ACE Fase 2 — Baseline Runtime Execution & PR #67 Autonomy Audit

**Base `main` SHA:** `80104ce50ecbcea21080bed8c0eabce88d47ccb5`
**Evidence JSON:** `evidence/phase2/ace_base_runtime_baseline_20261107.json`

---

## 1. Tiga Status Bukti (Pemisahan Wajib)

| Jenis Status | Nilai Fase 2 | Makna Aktual pada Fase Ini |
|---|---|---|
| `ACE_BASE_RUNTIME_EXECUTED` | **`TRUE`** | `ace.py demo`, `ace.py status` (termasuk pembukaan ulang lintas proses Python 3.12 → 3.13), `tools/verify_sources.py` (`25/25`), dan `ace_runtime.test_engine` + `test_cli` (`17/17` pada Python 3.12 & 3.13) dieksekusi nyata. |
| `NEW_CAPABILITY_INTEGRATED_AND_EXECUTED` | **`TRUE` (Spike PR #67 diaudit)** | Prototipe `code/ace_autonomy/core.py` pada `d7b311ab883bc6f58e75a271d064aa4850bc1930` dieksekusi lokal pada Python 3.12 & 3.13 (`11/11` tes lulus, termasuk pemanggilan `ace_runtime` asli via `RealACEIntegration.test_actual_runtime_demo`). |
| `SCIENTIFIC_CAPABILITY_VALIDATED` | **`FALSE` (`NOT_ASSESSED`)** | Demo simbolik `a/b` (`source_equal`, `inherited_equal`, `changed_ends`) hanya memvalidasi ketahanan rekayasa & pewarisan program identik, **bukan** perbaikan software umum maupun penemuan representasi baru. |

---

## 2. Verifikasi Baseline Nyata (`code/ace_runtime/`)

1. **Integritas Source (`tools/verify_sources.py`)**: `PASS: 25 imported files match their recorded Git blob IDs (offline)`.
2. **Implementation Digest**: `931b1582e4dc9579a56712936097a9d476941cdc1bc19c876f6ea4936aab644c`.
3. **Hasil `ace.py demo` & `ace.py status`**:
   - SHA-256 output `demo`: `5068df35272067020e24fffcc7de0fa7991f953c94e0cd7e61af0966dc0f3e42`.
   - SHA-256 output `status` (Python 3.12 dan setelah restart di Python 3.13): `0b1c0dd0ecbf86c31c658bd5eb147fdfe01b4d4be7416ff366dddd25061d85ea` (identik byte-per-byte).
   - Ringkasan tugas:
     - `source_equal` (`7f34e0ab...`): `LEARNED_STAGED` (`learning_called=true`), model `7c6506bd...`, train `63/63`, val `128/128`, terminal `128/128` (`predictions_sha256: db79b0bf...`).
     - `inherited_equal` (`563d54e0...`): `REUSE_VALIDATED` (`learning_called=false` — **model diwariskan tanpa refit**), model `7c6506bd...`, train `63/63`, val `128/128`, terminal `128/128` (`predictions_sha256: 385bc3db...`).
     - `changed_ends` (`8ef5a29c...`): `LEARNED_STAGED` (`learning_called=true` — **dilatih ulang** karena aturan berubah), model `3e5b5b32...`, train `63/63`, val `128/128`, terminal `128/128` (`predictions_sha256: d0b8586e...`).
   - Penyimpanan pasca-restart: `2` kapabilitas tersimpan, `3` evaluasi terminal tercatat, `9` event berantai hash utuh tanpa korupsi WAL.

---

## 3. Audit Teknis PR #67 vs `engineering/ace-autonomy-core-v01`

### 3.1 Hubungan Git & Bukti CI
- Branch Codex `origin/engineering/ace-autonomy-core-v01` (`d545083a27a820a6507741a24e190024998b07b7`) berisi komit pra-registrasi `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md` (`sha256: b7a540c73fb20df4a6787fccaf48ad409465a411d944ddaa3cc62c28cdaddcbc`).
- PR #67 (`origin/engineering/chat-ace-autonomy-prototype-20261107` @ `d7b311ab883bc6f58e75a271d064aa4850bc1930`) merupakan *fast-forward descendant* langsung di atas `d545083a` yang menambahkan implementasi awal `code/ace_autonomy/{core.py, cli.py, test_core.py}`, `autonomy.py`, `docs/ACE_AUTONOMY_PROTOTYPE_RESULTS.md`, dan `.github/workflows/ace-autonomy.yml`.
- GitHub Actions Run `#42346508018` (`autonomy (3.12)` dan `autonomy (3.13)`) diverifikasi `SUCCESS`, dan direproduksi secara lokal pada Python `3.12.16` serta `3.13.18` (`11/11` tes lulus).

### 3.2 Keputusan Jalur Implementasi Utama (Lane A)
Kami memilih **`d7b311ab883bc6f58e75a271d064aa4850bc1930` sebagai titik berangkat silsilah branch Lane A** (yang secara otomatis melestarikan komit `d545083a` dari `engineering/ace-autonomy-core-v01` sebagai parent-nya), **namun tidak menggabungkannya mentah-mentah**, karena audit kode menemukan **12 celah rekayasa dan keamanan** yang wajib diperbaiki pada Fase 3:

1. **Race inisialisasi `.host_key`**: `O_CREAT | O_EXCL` membuat berkas 0-byte sebelum menulis 32 byte kunci; worker kedua yang masuk bersamaan membaca 0 byte dan gagal.
2. **Belum ada penegakan anggaran nyata**: `max_steps`, `max_candidates`, `max_retries_per_step`, `wall_seconds` (`time.monotonic`), dan `cpu_seconds` (`RUSAGE_SELF + RUSAGE_CHILDREN` + `RLIMIT_CPU`) belum ditegakkan menuju status `BUDGET_EXHAUSTED`.
3. **Lock tulis SQLite global selama eksekusi tool**: `_dispatch` dijalankan di dalam `BEGIN IMMEDIATE`, memblokir konkurensi nyata; harus diganti model **lease 3-fase** (`CLAIM/DISPATCH` → eksekusi terbatas → `VERIFY/COMMIT`) dengan `lease_owner`, `lease_epoch` monotonik, dan `lease_expires_at`.
4. **Belum ada protokol escrow `HALT_UNCERTAIN` untuk aksi eksternal**: Aksi eksternal yang *crash* atau kedaluwarsa sesudah `DISPATCHED` tetapi sebelum bukti penerimaan terverifikasi tidak boleh di-retry otomatis (mitigasi `PR #33` & `RT-07`).
5. **`IntegrityError` mewarisi `ValueError` sehingga tertelan**: `except (PolicyError, ValueError, ...)` menangkap `IntegrityError` (baik dari `ace_autonomy` maupun `ace_runtime`) sebagai kegagalan langkah biasa alih-alih menghentikan eksekusi secara *fail-closed*.
6. **Pemeriksaan `Path.is_symlink()` mati sesudah `resolve()`, rentan symlink leluhur (`RT-03`) & hang FIFO (`RT-08`)**: Harus diganti pembacaan komponen-demi-komponen dengan `os.open(..., O_RDONLY | O_NOFOLLOW | O_NONBLOCK, dir_fd=...)` dan pemeriksaan `stat.S_ISREG`.
7. **Rentan *valid-prefix tail rollback* (`RT-07`)**: Pemotongan baris terakhir tabel `events`/`receipts` tidak terdeteksi saat dibuka ulang tanpa jangkar kepala rantai eksternal bertanda tangan HMAC (`chain_head.json`).
8. **Kanonikalisasi tipe longgar (`RT-11`, `RT-13`) & transisi state belum ketat (`RT-02`, `RT-10`)**: Perlu penegakan `type(x) is int` / `bool` dan otomata transisi state eksplisit mencakup `STAGED_FOR_REVIEW` dan `HALT_UNCERTAIN`.
9. **Digest implementasi belum mencakup modul transitif & validasi asal path `ace_runtime`**.
10. **Skema `GoalPolicy` (`ace.goal.v1` + kompatibilitas `ace.goal.v01`)** belum menegakkan `read_paths`, `write_paths` khusus staging, `review_policy`, dan `stop_on_uncertain_external_action`.
11. **Belum ada pemisahan eksplisit `Verifier` independen & `CapabilityRegistry`**.
12. **Cakupan tool `ace_runtime` baru sebatas `ace_status` dan `ace_demo`**: Perlu diperluas ke operasi penuh (`ace_enqueue_task`, `ace_run_tasks`, `ace_predict`, `ace_evaluate`, `ace_report`, staging kandidat terisolasi, dan suite tes tepercaya).
