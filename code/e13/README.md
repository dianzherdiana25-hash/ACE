# E1.3 development — checkpoint v0.1

Dua fixture publik menguji jalur `fit → predict → score` untuk transformasi simbolik dan graf beratribut. Pembanding development memilih dari tiga AST tetap per keluarga dengan membandingkan keluaran demonstrasi target, lalu demonstrasi sumber sebagai pemutus seri. Setiap keluarga mempunyai tiga probe. Operasi target fixture tersedia di katalog pembanding agar fixture menguji mekanik harness.

Jalankan dari root repo dengan Python 3.10+ tanpa dependensi pihak ketiga.

```bash
PYTHONPATH=code python3 -m unittest -v e13.test_development
PYTHONPATH=code python3 -m e13.development
python3 verify_handoff.py
```

## Kontrak JSON v1

| Objek | Field dan batas |
| --- | --- |
| Request `fit` | `version` bernilai 1, `task_id` 32 karakter hex huruf kecil, `family` S atau G, `seed` uint32, `fuel` 1–100.000, `source` dan `target` masing-masing 1–16 objek demonstrasi `{input, output}`. Maksimum 32 KiB. Seed dicatat dan enumerator berurutan deterministik. |
| I/O S | Array maksimal 64 token bilangan bulat 0–15. `pair_flags` mengeluarkan 0 atau 1 untuk setiap pasangan bersebelahan. |
| Input G | Graf berarah dengan `nodes` 1–16, `start` dan `goal` sebagai indeks simpul, serta hingga 64 sisi `[awal, akhir, label, biaya]`. Label 0–3 dan biaya 0–15. |
| Output G | Biaya lintasan minimum atau `null` jika tak terjangkau. |
| AST S | `{"family":"S","ast":{"op":"pair_flags","rule":{"op":"lt"}}}`. Pilihan aturan `eq`, `lt`, `gt`. |
| AST G | `{"family":"G","ast":{"op":"path_cost","rule":{"op":"different"}}}`. Pilihan aturan `any`, `different`, `same`. |
| Input `predict` | Satu JSON I/O tanpa label, maksimum 4 KiB, plus AST yang dikanonisasi saat compile. AST dibatasi 1 KiB dengan struktur bertingkat tetap dan diikat dengan SHA-256. |

Parser menolak field tambahan, kunci ganda, tipe salah, dan operasi di luar katalog. Interpreter menghitung satu langkah pada eksekusi awal, per pasangan token, serta per sisi yang disiapkan, entri antrean yang diambil, dan sisi yang diperiksa pada graf. Fit memakai satu anggaran untuk seluruh katalog. Semua probe satu fixture berbagi anggaran prediksi tersendiri.

## Bukti dan batas

- **10/10 tes lulus** pada Python 3.12, termasuk perubahan label probe yang tidak mengubah masukan fit atau SHA AST, penolakan probe berlabel, batas bahan bakar, dan 80 perbandingan dengan referensi graf berbasis relaksasi.
- **6/6 probe publik cocok**, dengan 27 dan 58 langkah fit masing-masing untuk S dan G. Pemeriksaan SHA atas **45/45** berkas historis lulus.
- Uji pemisahan mencakup antarmuka JSON di proses development. Isolasi jaringan dan berkas, kontrol penelitian lengkap, CPU/wall/RSS, bank selection, dan evaluator tersegel masih menjadi pekerjaan berikutnya. Konfirmasi tetap ditahan.

Lanjutkan dari [desain E1.3](../../design/e1.3/E13_DESIGN_v0.1.md). Unit berikutnya adalah pemisahan jalur kandidat dan evaluator, dengan uji akses sumber data, canary, dan pemeriksaan duplikasi aturan lintas split.
