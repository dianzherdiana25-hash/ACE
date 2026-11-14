# Laporan Pra-Audit Mekanis — s3-dev-pilot (PR #184 dev harness outputs, band 20261501 witnesses)

> PRE-AUDIT MEKANIS — bukan persetujuan, bukan validasi eksperimen. Laporan ini hanya menyatakan hasil perbandingan mekanis atas paket beku terhadap manifest eksplisit. Keadaan SESUAI pada semua cek tidak berarti eksperimen sah, benar, atau disetujui.

Validator: preaudit-validator-2.1.0 · Manifest SHA-256: `db8bb3e2e28f4283a68e511ff0f9b368e13fe1b590f1371dd9b16fb9f36ae278`

Validation spec digest: `5b0ea067692683b234a8d47cb7ae80262e018e00174d0f91fa4cc30ebb8ed2e0`

Siklus hidup: STAGED → REGISTERED OBSERVATION → VALIDATION VERDICT → PUBLISHED RESULT · Masukan: REGISTERED OBSERVATION · Keluaran: VALIDATION VERDICT · Tidak dilakukan: PUBLISHED RESULT

Ringkasan (hitungan keadaan per cek — bukan persetujuan): {'SESUAI': 2, 'TIDAK SESUAI': 0, 'UNKNOWN': 2}

## C1 — Artifact completeness + hash integrity: **SESUAI**

- [SESUAI] cell_control.json — present, 4632 bytes, sha256 matches manifest (kode: OK)
- [SESUAI] cell_frontier_only.json — present, 4638 bytes, sha256 matches manifest (kode: OK)
- [SESUAI] cell_rounds_only.json — present, 4637 bytes, sha256 matches manifest (kode: OK)
- Dependensi: the manifest itself (its custody is out of scope)
- Kelas false-positive: canonicalization/path errors (symlink, separator, case) — measured by valid-variant probes
- Langkah berikut: No action for matching artifacts. For any TIDAK SESUAI: re-freeze the package or correct the manifest, then re-run. For UNKNOWN: repair the manifest entry.

## C2 — Result-count consistency (declared recomputations only): **UNKNOWN**

- [UNKNOWN] manifest.count_assertions — no count assertions declared; the validator invents no formula of its own (kode: NOT_DECLARED)
- Bukti kurang: manifest.count_assertions
- Kelas false-positive: numeric-representation brittleness (0 vs 0.0 vs 1e2) — measured by valid-variant probes
- Langkah berikut: Declare the mechanical recomputations to check, or accept UNKNOWN for C2.

## C3 — Verdict vs preregistration rule: **UNKNOWN**

- [UNKNOWN] manifest.verdict_check — no verdict check declared in the manifest (kode: NOT_DECLARED)
- Bukti kurang: manifest.verdict_check
- Kelas false-positive: rule-shape rigidity — unsupported rule shapes fail toward UNKNOWN, never toward false TIDAK SESUAI
- Langkah berikut: Declare preregistration + results artifacts, or accept UNKNOWN for C3.

## C4 — Stage-3 artifact consistency (task maps + frontier provenance): **SESUAI**

- [SESUAI] task_map[0] — 2 records decidable, 0 solved, no contradictions (kode: OK)
- [SESUAI] task_map[1] — 2 records decidable, 0 solved, no contradictions (kode: OK)
- [SESUAI] task_map[2] — 2 records decidable, 0 solved, no contradictions (kode: OK)
- [SESUAI] frontier_log[0] — 6 rounds: sequence intact, counts consistent, provenance resolvable (kode: OK)
- [SESUAI] frontier_log[1] — 3 rounds: sequence intact, counts consistent, provenance resolvable (kode: OK)
- Dependensi: C1 integrity of every artifact C4 touches; stage3_check declared in the manifest
- Kelas false-positive: shape rigidity of the Stage-3 artifact forms (task maps, frontier logs) — fails toward UNKNOWN; measured on PR #184 dev-harness shapes
- Langkah berikut: For TIDAK SESUAI: the named record/round contradicts the declared Stage-3 shapes on complete inputs. For UNKNOWN: supply the missing shape or identity fields; the checker does not guess them.

## Batas jujur
- Proves the package matches its manifest on the declared mechanical checks only.
- Does not prove the manifest is the right manifest, that the preregistration predates the results, or that declared recomputations are scientifically correct.
- Does not approve or validate any experiment, result, or gate claim.

Berkas dalam pohon sumber yang tidak terdaftar di manifest (informasi saja, bukan masukan vonis): 0
