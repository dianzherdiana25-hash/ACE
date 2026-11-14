# ACE — audit perubahan berkas PR lama #15–#33

Snapshot 2026-11-13 05:48:47 UTC. Audit baca-saja atas PR terbuka dalam rentang
nomor tersebut menghasilkan **18 PR**: semuanya open draft pada readback GitHub.
**17 PR** mengubah Python non-test beserta berkas tes; **#32** mengubah Python
non-test tanpa perubahan berkas tes. Tidak ada PR khusus dokumen dalam sampel ini.
Sumber seluruh hitungan: [snapshot terpin](../../evidence/audit_20261113_legacy_prs/path_inventory.json),
field `summary` dan `pulls`. Status ini hanya berlaku pada waktu snapshot.

Main terpin: [`bb22c44b5563a680190c06a89f2c7004d3ada8ec`](https://github.com/dianzherdiana25-hash/ACE/commit/bb22c44b5563a680190c06a89f2c7004d3ada8ec).
Orientasi sesi memakai README, peta source, dan Addendum 58 pada commit itu.
Audit ini menambahkan inventaris historis yang terpisah dari
[audit #95–#102 sebelumnya](ACE_OMEGA_PR_AUDIT_20261111.md).

## Metode dan batas

- Metadata base/head/state/draft diambil dari GitHub; changed filenames memakai
  konektor yang membaca seluruh halaman. Snapshot menyimpan field teknis yang
  diperlukan, tanpa body PR atau identitas pembuatnya.
- Setiap daftar jalur dicocokkan dengan `git diff --no-renames --name-status`
  dari merge-base base/head terpin ke head. **18/18 cocok**; SHA lengkap,
  status perubahan, dan tree entry git tersimpan per berkas.
- `python_test` berarti basename `.py` diawali `test_` atau diakhiri `_test.py`.
  Python lain masuk `python_non_test`, termasuk `__init__.py` dan harness
  verifikasi. Ini klasifikasi nama berkas; cakupan perilaku belum dinilai.
- Hitungan adalah delta terhadap base masing-masing. Satu jalur dapat muncul
  pada beberapa PR: **210 kemunculan, 196 jalur unik**. Jangan menjumlahkan
  kemunculan sebagai modul atau kemampuan independen.
- File bukti lama hanya dicatat jalur/hash git-nya; isinya tidak diputar ulang.
  Kelulusan tes terkini dan kebenaran klaim ilmiah: **TIDAK TAHU**.

## Peta delta

Kolom Py = Python non-test; Tes = berkas Python bernama tes; CI = workflow;
Data = data desain dan manifest lain. Seluruh angka merujuk `pulls[].category_counts`
dalam [snapshot](../../evidence/audit_20261113_legacy_prs/path_inventory.json).
Tautan head terpin; nomor PR merujuk halaman PR yang dapat berubah.

| PR | Head terpin | Dokumen | Bukti | Py | Tes | CI | Data |
|---|---|---:|---:|---:|---:|---:|---:|
| [15](https://github.com/dianzherdiana25-hash/ACE/pull/15) | [cb295d2](https://github.com/dianzherdiana25-hash/ACE/commit/cb295d2cf0413f2f1008307ed8d8b72ce3600049) | 8 | 10 | 12 | 8 | 0 | 1 |
| [16](https://github.com/dianzherdiana25-hash/ACE/pull/16) | [518827c](https://github.com/dianzherdiana25-hash/ACE/commit/518827c5b7635f1d8d097e1b927c5f4b96aedf45) | 3 | 1 | 6 | 3 | 0 | 0 |
| [18](https://github.com/dianzherdiana25-hash/ACE/pull/18) | [da071eb](https://github.com/dianzherdiana25-hash/ACE/commit/da071eb87bc050f803ed5fe66f018fac866c1f86) | 2 | 0 | 4 | 3 | 0 | 0 |
| [19](https://github.com/dianzherdiana25-hash/ACE/pull/19) | [63633f5](https://github.com/dianzherdiana25-hash/ACE/commit/63633f5dbff3f3153b9e36dba5b438aadcad7f6f) | 3 | 1 | 7 | 3 | 0 | 0 |
| [20](https://github.com/dianzherdiana25-hash/ACE/pull/20) | [864f49f](https://github.com/dianzherdiana25-hash/ACE/commit/864f49f4f3259814ac00de8ac49b59a61768647b) | 2 | 8 | 4 | 3 | 0 | 0 |
| [21](https://github.com/dianzherdiana25-hash/ACE/pull/21) | [9341874](https://github.com/dianzherdiana25-hash/ACE/commit/93418742f830a5437667f825f16682bc91822529) | 2 | 10 | 8 | 3 | 0 | 2 |
| [22](https://github.com/dianzherdiana25-hash/ACE/pull/22) | [988b077](https://github.com/dianzherdiana25-hash/ACE/commit/988b077dc2ff12d01d1f93fd6b1dca94036cc579) | 2 | 0 | 3 | 2 | 0 | 0 |
| [23](https://github.com/dianzherdiana25-hash/ACE/pull/23) | [c2fa5ec](https://github.com/dianzherdiana25-hash/ACE/commit/c2fa5ecea43d9bfb6d1c915a73c189d6af846c15) | 2 | 11 | 6 | 3 | 0 | 2 |
| [24](https://github.com/dianzherdiana25-hash/ACE/pull/24) | [1c16c6a](https://github.com/dianzherdiana25-hash/ACE/commit/1c16c6aa24907645ad303047fc728d627ba4af0f) | 1 | 0 | 2 | 2 | 0 | 0 |
| [25](https://github.com/dianzherdiana25-hash/ACE/pull/25) | [1359ebb](https://github.com/dianzherdiana25-hash/ACE/commit/1359ebbea0cc0e3e21aa9b4380347025d9a8165d) | 3 | 2 | 6 | 3 | 0 | 0 |
| [26](https://github.com/dianzherdiana25-hash/ACE/pull/26) | [aba67d6](https://github.com/dianzherdiana25-hash/ACE/commit/aba67d6c7572550b84ff464eba850cf2b6fdccc7) | 1 | 2 | 5 | 4 | 1 | 0 |
| [27](https://github.com/dianzherdiana25-hash/ACE/pull/27) | [9656407](https://github.com/dianzherdiana25-hash/ACE/commit/965640786cbf2f8adcd89eb1d980945f78c2da77) | 1 | 0 | 1 | 1 | 1 | 0 |
| [28](https://github.com/dianzherdiana25-hash/ACE/pull/28) | [4366fb6](https://github.com/dianzherdiana25-hash/ACE/commit/4366fb6aed548eb44838ac3be2b1f85e801b0725) | 1 | 0 | 1 | 1 | 0 | 0 |
| [29](https://github.com/dianzherdiana25-hash/ACE/pull/29) | [3ebed0a](https://github.com/dianzherdiana25-hash/ACE/commit/3ebed0a6dece19c603f4e56e2fddc29722fda79c) | 1 | 2 | 1 | 1 | 1 | 0 |
| [30](https://github.com/dianzherdiana25-hash/ACE/pull/30) | [ff77cbe](https://github.com/dianzherdiana25-hash/ACE/commit/ff77cbef72e5b813c1abf85500dfdf0d2173ace8) | 1 | 0 | 2 | 4 | 0 | 0 |
| [31](https://github.com/dianzherdiana25-hash/ACE/pull/31) | [08c8233](https://github.com/dianzherdiana25-hash/ACE/commit/08c8233e6641eab2fc2ab1a48ab6c9cb4a4e564a) | 1 | 0 | 3 | 1 | 0 | 0 |
| [32](https://github.com/dianzherdiana25-hash/ACE/pull/32) | [f507229](https://github.com/dianzherdiana25-hash/ACE/commit/f50722919d59772ae2f0bcc5eafc04aba1d7d5ff) | 0 | 0 | 1 | 0 | 1 | 0 |
| [33](https://github.com/dianzherdiana25-hash/ACE/pull/33) | [2aa08f7](https://github.com/dianzherdiana25-hash/ACE/commit/2aa08f78201ed3c4578ed4489e48ce132aaf9033) | 0 | 0 | 2 | 1 | 0 | 0 |

## Temuan yang perlu dipertahankan saat triase

1. **#32 memakai tes warisan.** [Runner terpin](https://github.com/dianzherdiana25-hash/ACE/blob/f50722919d59772ae2f0bcc5eafc04aba1d7d5ff/tools/ace_ci_exact_head.py)
   mendeklarasikan `ace_loop.test_source_evolution`, `ace_loop.test_engine`,
   dan `ace_loop.test_portfolio`. Label audit yang didukung adalah
   “tanpa perubahan berkas tes dalam diff”. Hasil eksekusinya belum diperiksa.
2. **#30 memiliki harness verifikasi di luar pola nama tes.**
   [verify_expected_failures.py terpin](https://github.com/dianzherdiana25-hash/ACE/blob/ff77cbef72e5b813c1abf85500dfdf0d2173ace8/code/ace_redteam/verify_expected_failures.py)
   memeriksa identitas source dan tanda kegagalan yang diharapkan. Ia masuk
   Python non-test pada tabel; keberadaannya tidak menambah klaim kemampuan.
3. **Stack dan jalur bersama memerlukan rekonsiliasi.** #25 berbasis #24;
   #26/#27 berbasis #25; #28/#30/#31/#32/#33 berbasis #27. #26 dan #27 sama-sama
   mengubah `code/ace_loop/source_evolution.py` beserta tesnya. #22 dan #23
   berbagi jalur audit E14Z. Peta lengkap: `base_ref`, `base_sha`, dan
   `shared_python_paths` dalam snapshot. Kesamaan jalur belum membuktikan
   konflik tekstual atau kesetaraan implementasi.
4. **Ancestry dan integrasi semantik harus dinilai terpisah.** Pemeriksaan
   `git merge-base --is-ancestor` memberi **0/18** head sebagai leluhur main
   terpin. Snapshot juga mencatat perbandingan tree entry pada jalur yang sama.
   [README terpin](https://github.com/dianzherdiana25-hash/ACE/blob/bb22c44b5563a680190c06a89f2c7004d3ada8ec/README.md)
   dan [manifest impor](https://github.com/dianzherdiana25-hash/ACE/blob/bb22c44b5563a680190c06a89f2c7004d3ada8ec/docs/UPSTREAM_SOURCES.json)
   menjelaskan integrasi terpilih. Kode yang dipindah atau diadaptasi belum
   direkonsiliasi oleh audit ini; status integrasi semantik **TIDAK TAHU**.

## Pengulangan pemeriksaan

Jalankan dari root checkout dengan commit terpin tersedia. Pemeriksa hanya
membaca snapshot dan metadata git; tidak mengimpor source ACE, memanggil model,
atau menjalankan suite/eksperimen. Commit yang tidak tersedia menghasilkan gagal.
Kesamaan metadata GitHub pada waktu snapshot tetap memerlukan readback GitHub;
pemeriksaan offline hanya mencocokkan daftar API yang disimpan dengan git.

```sh
sha256sum evidence/audit_20261113_legacy_prs/path_inventory.json
python3 evidence/audit_20261113_legacy_prs/verify_inventory.py
```

SHA256 snapshot: `0e2987210f2534287a4fa9e01fafc8e65783825c5df19251b4e62763d2d81815`.
[Log pemeriksaan](../../evidence/audit_20261113_legacy_prs/verification.log)
mencatat `PATH_INVENTORY_MATCH` dan kontrol negatif yang menolak hash blob
yang sengaja diubah pada salinan sementara. Hash pemeriksa juga dicatat di log.
Tidak ada suite historis yang dijalankan untuk audit ini.

SELESAI: peta delta, SHA dan tree entry terpin, serta pemeriksaan ulang baca-saja
tersimpan pada [paket bukti](../../evidence/audit_20261113_legacy_prs/).

TERSISA: penilaian cakupan perilaku dan rekonsiliasi semantik hanya bila dipilih
sebagai tugas terpisah; audit ini tidak menetapkan urutan integrasi.

PENGHAMBAT: tidak ada untuk inventaris jalur. Kelulusan/cakupan tes dan klaim
ilmiah tetap TIDAK TAHU; memerlukan evaluasi source/tes dan bukti yang terpisah.
