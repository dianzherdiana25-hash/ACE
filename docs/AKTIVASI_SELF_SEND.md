# Aktivasi Self-Send ACE (khusus operator)

> **PERINGATAN — HANYA OPERATOR.** Dokumen ini untuk operator manusia.
> Agen/engine tidak boleh membuat marker aktivasi sendiri. Self-send hanya
> membuka DRAFT PR; tidak pernah merge, tidak pernah ke `main`.

Sumber kebenaran: `code/ace_operational/self_send.py`. Dokumen ini hanya
mengutip konstantanya; tes `tools/test_docs_self_send_e7.py` memastikan kutipan
tetap cocok dengan kode.

## Prasyarat

- Repo target: `dianzherdiana25-hash/ACE` (`EXPECTED_REPO`), basis `main` (`BASE_BRANCH`).
- `gh` terautentikasi dan sehat (jika tidak: `gh_auth_unhealthy`).
- Worktree bersih (jika tidak: `worktree_dirty`).
- Berkas hanya di bawah `handover/` atau `evidence/` (`ALLOWED_PATH_PREFIXES`).
- Jalur yang memuat fragmen denylist ditolak: `ledger_penghasilan`, `utang_awal`,
  `secret`, `credential`, `.env`, `.ace-llm-token`, `id_rsa`, `.pem`, `.key`.
- Cabang bernama `ace-auto/<YYYYMMDD>-<slug>` (`BRANCH_PREFIX = "ace-auto/"`),
  slug `^[a-z0-9][a-z0-9-]{0,40}$`.

## Mekanisme

- Fetch: `+refs/heads/main:refs/ace-self-send/base` (`FETCH_REFSPEC`, ref `BASIS_REF`).
- PR dibuat hanya dengan `--draft --base main`.
- Audit lokal: `<HOME>/self_send_audit.jsonl`; salinan repo: `handover/self_send_audit.jsonl` (`AUDIT_REPO_PATH`).
- Berkas ack: `self_send_acked.json` (`ACK_NAME`).
- Kelas ratifikasi: `verdict_sealed`, `mission_ratified`, `skill_verified`.

## Aktivasi (terawasi)

1. Pastikan prasyarat di atas terpenuhi.
2. Uji kirim terawasi: operator menyaksikan satu `send(...)` dengan berkas sepele
   di `handover/`, lalu memeriksa PR draft yang muncul dan baris audit-nya.
3. Hanya setelah itu buat marker kosong: `touch <HOME>/ACE_SELF_SEND_ENABLED`
   (`MARKER_NAME`). Tanpa marker, setiap pengiriman ditolak `marker_absent`.

## Kondisi berhenti

Hentikan dan hapus marker bila: PR tak terduga muncul, audit mencatat
penolakan berulang, `gh_auth_unhealthy`, `fetch_target_mismatch`, atau
`push_target_mismatch` (target repo tidak sesuai).

## Rollback

1. `rm <HOME>/ACE_SELF_SEND_ENABLED` — efek segera, semua kirim berikutnya `refused:marker_absent`.
2. Tutup PR draft `ace-auto/*` yang tersisa dan hapus cabangnya secara manual.
3. Audit tidak dihapus (jejak).

## Kode penolakan

`marker_absent`, `governance:<exc>`, `fetch_target_mismatch`,
`push_target_mismatch`, `gh_auth_unhealthy`, `fetch_failed:<err>`,
`base_main_missing`, `worktree_dirty`, `duplicate_branch`,
`branch_create_failed:<err>`, `commit_failed:<err>`,
`outgoing_validation_failed`, `push_failed:<err>`.
Setiap penolakan dicatat sebagai outcome `refused:<reason>`.
