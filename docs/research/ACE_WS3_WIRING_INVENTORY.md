# Inventaris wiring WS-3

Snapshot source `95cee1209265286df250bebb8a0fea7ae0bcb422`. Pemeriksaan
referensi statis pada `code/` dan `tools/` tanpa tes, ditambah penelusuran
entry point dari paket KBM, loop ratifikasi, dan helper memori. Referensi
dinamis di luar checkout dan status runtime TIDAK TAHU.

| Simbol | Bukti di snapshot | Keputusan |
|---|---|---|
| `cover_check.check_cover` | Dipakai CLI sampul dan adaptor fuzz. `kbm_pack_check.check_package` hanya memeriksa magic bytes. | Hubungkan lewat opsi `--strict-cover` pada pemeriksaan paket lokal. |
| `profiling_observer.instrumented_solver` | Dipakai pilot pengembangan di modul yang sama. Modul mendeskripsikan observasi di luar keputusan solver. | Pertahankan sebagai pilot terpisah. |
| `preaudit_oracle.oracle_expected_verdict` | Referensi runtime langsung tidak ditemukan. Oracle mendeskripsikan pemeriksaan independen. | Daftarkan sebagai bantuan verifikasi, kepastian pemakaian eksternal TIDAK TAHU. |
| `ratification_loop.run_ratification_episode(context=…)` | Engine memanggil fungsi ini tanpa context. Modul mendokumentasikan seam injeksi. | Tunggu rancangan hub dan aturan pemilihan konteks. |
| `memory_writeback.record_event_outcomes` | Dipanggil dari dua keluaran verifier evolusi. | Sudah terhubung. |
| `ConversationalMemoryManager.build_prompt_context` | Dipanggil `language.py` pada jalur percakapan. | Sudah terhubung. |

```sh
python3 -m tools.kbm_pack_check /tmp/existing-local-package --strict-cover
PYTHONPATH=code:. python3 -m unittest tools.test_kbm_cover_wiring tools.test_cover_check tools.test_kbm_pack_check -q
```

SELESAI — 11 tes lulus, termasuk CLI yang menolak sampul terlalu kecil.
Aturan lokal memakai validator yang ada. Pemeriksaan membaca metadata header
gambar. Pemeriksaan konten gambar dan penerimaan platform berada di luar bukti.

TERSISA — usulan isi ulang berupa peta call site lebih luas untuk seam
direktur dan scheduler saat kontrak hub tersedia.

PENGHAMBAT — aktivasi seam eksperimen atau runtime memerlukan rancangan
dan otorisasi yang berlaku pada seam tersebut.
