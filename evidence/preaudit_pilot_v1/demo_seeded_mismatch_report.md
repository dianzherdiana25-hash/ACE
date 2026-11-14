# Laporan Pra-Audit Mekanis — DEMO-SEEDED-MISMATCH (copy of abc-v3-01 with verdict flipped; not a real package)

> PRE-AUDIT MEKANIS — bukan persetujuan, bukan validasi eksperimen. Laporan ini hanya menyatakan hasil perbandingan mekanis atas paket beku terhadap manifest eksplisit. Keadaan SESUAI pada semua cek tidak berarti eksperimen sah, benar, atau disetujui.

Validator: preaudit-validator-1.0.0 · Manifest SHA-256: `26d2f757bda83a63df66909d7fdcd7708e76e50a04df7a115710c164bf361b6b`

Ringkasan (hitungan keadaan per cek — bukan persetujuan): {'SESUAI': 2, 'TIDAK SESUAI': 1, 'UNKNOWN': 0}

## C1 — Artifact completeness + hash integrity: **SESUAI**

- [SESUAI] evidence/abc-v3-kernel/custody.json — present, 921 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-kernel/preregistrations/abc-v3-01.json — present, 1206 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-kernel/results.jsonl — present, 1204 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261501_A.json — present, 99 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261501_B.json — present, 12885 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261501_C.json — present, 100 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261502_A.json — present, 99 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261502_B.json — present, 12639 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261502_C.json — present, 100 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261503_A.json — present, 99 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261503_B.json — present, 12885 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/arm_20261503_C.json — present, 100 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/band_20261501.json — present, 2206 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/band_20261502.json — present, 2078 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/band_20261503.json — present, 2106 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/discovery_20261501.json — present, 4278 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/discovery_20261502.json — present, 1856 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/discovery_20261503.json — present, 1667 bytes, sha256 matches manifest
- [SESUAI] evidence/abc-v3-run-state/heartbeat.json — present, 96 bytes, sha256 matches manifest
- [SESUAI] evidence/abc_v3_finalize.json — present, 3126 bytes, sha256 matches manifest
- [SESUAI] evidence/abc_v3_preregistration_record.json — present, 574 bytes, sha256 matches manifest
- [SESUAI] evidence/abc_v3_run.json — present, 8882 bytes, sha256 matches manifest
- [SESUAI] evidence/abc_v3_run_notes.json — present, 5552 bytes, sha256 matches manifest
- Dependensi: the manifest itself (its custody is out of scope)
- Kelas false-positive: canonicalization/path errors (symlink, separator, case) — measured by valid-variant probes
- Langkah berikut: No action for matching artifacts. For any TIDAK SESUAI: re-freeze the package or correct the manifest, then re-run. For UNKNOWN: repair the manifest entry.

## C2 — Result-count consistency (declared recomputations only): **SESUAI**

- [SESUAI] bands-to-pooled-counts — summed pairs equal target: {"A": [0, 90], "B": [90, 90], "C": [90, 90]}
- [SESUAI] bands-to-pooled-control-counts — summed pairs equal target: {"A": [101, 101], "B": [99, 101], "C": [99, 101]}
- [SESUAI] pooled-rates-vs-finalize-arms — all rates within tolerance 0.000001: A (diff 0.0), B (diff 0.0), C (diff 0.0)
- [SESUAI] pooled-rates-vs-finalize-control — all rates within tolerance 0.000001: A (diff 0.0), B (diff 1.019801980198E-14), C (diff 1.019801980198E-14)
- [SESUAI] protocol-hash-results-vs-prereg — both sides equal: 8591b93814759d5485be3f9e8b47e31a08aa7b1fc41e14b2707b2aa46b975c1a
- [SESUAI] record-hash-results-vs-finalize — both sides equal: ebbfe054943c8de9546d743bdba55cd792082ad568119646dbd240a29582c8f5
- [SESUAI] di-results-vs-finalize — both sides equal: -1.9801980198019749
- Dependensi: C1 integrity of every artifact an assertion touches
- Kelas false-positive: numeric-representation brittleness (0 vs 0.0 vs 1e2) — measured by valid-variant probes
- Langkah berikut: For TIDAK SESUAI: the declared recomputation disagrees with the recorded values — inspect the named pointers. For UNKNOWN: supply the missing artifact/pointer or a supported assertion kind.

## C3 — Verdict vs preregistration rule: **TIDAK SESUAI**

- [TIDAK SESUAI] entry[0] — metric differentiation_index_pp=-1.9801980198019749 gte 0 -> expected fail, recorded pass
- Dependensi: C1 integrity of the preregistration and results artifacts; the preregistration rule shape {metric, op, threshold}
- Kelas false-positive: rule-shape rigidity — unsupported rule shapes fail toward UNKNOWN, never toward false TIDAK SESUAI
- Langkah berikut: For TIDAK SESUAI: the recorded verdict contradicts the preregistered rule on complete inputs. For UNKNOWN: supply the metric/rule in the supported shape, or record the entry's verdict as pass/fail.

## Batas jujur
- Proves the package matches its manifest on the declared mechanical checks only.
- Does not prove the manifest is the right manifest, that the preregistration predates the results, or that declared recomputations are scientifically correct.
- Does not approve or validate any experiment, result, or gate claim.

Berkas dalam pohon sumber yang tidak terdaftar di manifest (informasi saja, bukan masukan vonis): 0
