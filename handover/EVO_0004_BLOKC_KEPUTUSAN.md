# EVO 0004 Blok C — Keputusan Peran Sahabat-AI-9B

**Keputusan (dari angka T3 EVO 0003, PR #242):** Sahabat-AI-9B
adalah **organ on-demand untuk tugas batch Bahasa Indonesia** —
BUKAN anggota slate always-on, BUKAN hakim loop per-episode.

## Dasar terukur (bench 2026-11-16, rumah bekerja, llama-bench
## -p 512 -n 128 -r 3, llama.cpp b12316)

| konfigurasi | pp512 (t/s) | tg128 (t/s) |
|---|---|---|
| llama.cpp -t 1 | 6.03 ± 0.18 | 0.99 ± 0.09 |
| llama.cpp -t 8 | 31.79 ± 0.97 | 0.70 ± 0.07 |
| ik_llama -t 1 | 10.19 ± 0.39 | 0.90 ± 0.02 |

- tg ±0.9–1.0 t/s terlalu lambat untuk loop hakim per-episode
  (satu vonis butuh ratusan token → menit per episode di atas
  biaya proposer; slate sekarang menyelesaikan Blok A penuh
  dengan 0 errors).
- Kekuatan model ini adalah bahasa Indonesia (corpus CPT
  Sahabat-AI) dan pp ik_llama yang unggul (+69% vs stok pada
  -t 1) — cocok untuk pemrosesan batch dokumen/teks Indonesia
  yang tidak interaktif: diringkas, diterjemahkan, digenerate
  dalam antrian, bukan dalam loop keputusan.
- Slate always-on tidak berubah (front/coder/embedding +
  A3B on-demand). Tidak ada wiring layanan baru dari blok ini.

## Bukti fungsi

Satu smoke generation Bahasa Indonesia (prompt surat resmi
kepala desa, llama-cli b12316 -t 1, seed 42) — lihat
`evidence/evo0004/blokc_smoke.json`: verdict **SMOKE_OK**,
wall 131.9 dtk, footer sesi mencatat Generation 1.0 t/s
(konsisten T3). Berkas itu menyimpan tangkapan sesi mentah
(termasuk banner llama-cli); teks hasil sebenarnya:

> "Kepada Yth. Warga Desa [Nama Desa], dengan ini kami,
> Kepala Desa [Nama Desa], ingin memberitahukan jadwal
> gotong royong membersihkan saluran air pada hari Minggu,
> tanggal [Tanggal], pukul [Waktu] pagi. Kegiatan ini
> sangat penting untuk menjaga kelancaran aliran air dan
> mencegah banjir di desa kita. Kami berharap seluruh
> warga dapat berpartisipasi aktif dalam kegiatan ini
> untuk mewujudkan lingkungan yang bersih dan sehat bagi
> kita semua. Terima kasih atas perhatian dan partisipasi
> Bapak/Ibu."
