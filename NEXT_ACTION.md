# Aksi berikutnya untuk Work atau Codex

1. Mulai dari kepala `research/e1.3-design`. Baca [status](CURRENT_STATE.md), [rancangan prelock](design/e1.3/E13_PRELOCK_v0.1.md), [bukti reproduksi selection](evidence/e13/selection_reproduction_v1.json) dan [GitHub Issue #1](https://github.com/dianzherdiana25-hash/ACE/issues/1).
2. Siapkan runner konfirmatori dengan ledger arm idempoten, klasifikasi kegagalan dan uji interupsi/resume pada fixture publik. Siapkan STRUCTURED_ORACLE yang hanya tahu kelas grammar dan ukur biaya evaluator. Pertahankan solver beku dan B* beam.
3. Jalur evaluator membangun bank konfirmatori terpisah dan menunjukkan 48 blok independen per keluarga per rezim. Audit bentuk aturan, saksi, ambiguitas, dan duplikasi terhadap development dan selection. Simpan generator dan label di luar kandidat.
4. Verifikasi biaya/kuota, bekukan digest dan rencana analisis, lalu buka akses runner satu kali hanya setelah semua gerbang lulus. Bila kuota, blok efektif atau integritas split tidak cukup, catat HOLD.

Gunakan CPU lokal, anggaran Rp0, dan kontrak checkpoint pada [piagam](PROJECT_CHARTER.md).
