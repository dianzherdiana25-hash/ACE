# Laporan Pra-Audit Mekanis — bakeoff-records-intake (branch research/ace-omega-bakeoff-records-20261113 @ e8a3feb)

> PRE-AUDIT MEKANIS — bukan persetujuan, bukan validasi eksperimen. Laporan ini hanya menyatakan hasil perbandingan mekanis atas paket beku terhadap manifest eksplisit. Keadaan SESUAI pada semua cek tidak berarti eksperimen sah, benar, atau disetujui.

Validator: preaudit-validator-1.0.0 · Manifest SHA-256: `a8efd3d957ad929d61545602f25a6f6b74ba6c4e9cf4153b10dccb5e93f64602`

Ringkasan (hitungan keadaan per cek — bukan persetujuan): {'SESUAI': 1, 'TIDAK SESUAI': 0, 'UNKNOWN': 2}

## C1 — Artifact completeness + hash integrity: **SESUAI**

- [SESUAI] evidence/BAKEOFF02_RATIFIKASI_PREP_20261113.md — present, 5957 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_custody_harness.py — present, 3890 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_custody_record.json — present, 553 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_dryintake_fix_harness.py — present, 3403 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_dryintake_harness.py — present, 2621 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_dryintake_record.json — present, 682 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_intake_record.json — present, 2273 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_preregistration_record.json — present, 400 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff02_submit_harness.py — present, 2960 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff_arena30b_benchmark.json — present, 4120 bytes, sha256 matches manifest
- [SESUAI] evidence/bakeoff_arena30b_intake_record.json — present, 3050 bytes, sha256 matches manifest
- Dependensi: the manifest itself (its custody is out of scope)
- Kelas false-positive: canonicalization/path errors (symlink, separator, case) — measured by valid-variant probes
- Langkah berikut: No action for matching artifacts. For any TIDAK SESUAI: re-freeze the package or correct the manifest, then re-run. For UNKNOWN: repair the manifest entry.

## C2 — Result-count consistency (declared recomputations only): **UNKNOWN**

- [UNKNOWN] manifest.count_assertions — no count assertions declared; the validator invents no formula of its own
- Bukti kurang: manifest.count_assertions
- Kelas false-positive: numeric-representation brittleness (0 vs 0.0 vs 1e2) — measured by valid-variant probes
- Langkah berikut: Declare the mechanical recomputations to check, or accept UNKNOWN for C2.

## C3 — Verdict vs preregistration rule: **UNKNOWN**

- [UNKNOWN] manifest.verdict_check — no verdict check declared in the manifest
- Bukti kurang: manifest.verdict_check
- Kelas false-positive: rule-shape rigidity — unsupported rule shapes fail toward UNKNOWN, never toward false TIDAK SESUAI
- Langkah berikut: Declare preregistration + results artifacts, or accept UNKNOWN for C3.

## Batas jujur
- Proves the package matches its manifest on the declared mechanical checks only.
- Does not prove the manifest is the right manifest, that the preregistration predates the results, or that declared recomputations are scientifically correct.
- Does not approve or validate any experiment, result, or gate claim.

Berkas dalam pohon sumber yang tidak terdaftar di manifest (informasi saja, bukan masukan vonis): 0
