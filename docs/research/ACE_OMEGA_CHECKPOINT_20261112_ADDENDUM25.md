# ACE Ω — Addendum 25, 2026-11-12: Tahap C — Substrat Struktural Grid

PR #125 (draft, bertumpuk di atas #124). Diagnosis Addendum 21
(token-search 0/58 karena defek BFS bersifat struktural) dijawab
dengan substrat terkecil yang cocok dengan kelas defek terukur —
empat operator AST, satu per kelas, mengikuti pola pertumbuhan
substrat v2 untuk shipping:

- `restore_wall_guard` — menyisipkan kembali konjungsi
  `grid[..][..] != "#"` yang hilang (nama indeks dipulihkan dari uji
  dist yang selamat);
- `remove_diagonals` / `add_direction` — bedah tuple arah;
- `fix_start_offset` — konstanta jarak awal ke 0;

plus solver greedy berbasis skor shown (`solve_grid`).

**Probe pada set 58 tugas yang identik dengan pengukuran
token-search: 58/58 terselesaikan di holdout** — semua defek tunggal
dan semua pasangan — dalam waktu di bawah satu detik. Bug jujur
yang tertangkap probe dicatat di PR: `Budget.score` adalah cacah,
dan solver versi pertama berhenti pada kasus shown pertama yang
lulus; perbaikannya (parameter `shown_total` eksplisit) adalah
bagian dari hasil ini.

Status epistemik, apa adanya: operator ditulis terhadap katalog
defek yang dikenal — hasil ini membuktikan operator tingkat struktur
*menjangkau* kelas defek ini, bukan bahwa substratnya
menggeneralisasi ke defek tak dikenal. Pertanyaan generalisasi itu
adalah bahan semesta A/B/C grid kelak, bukan klaim addendum ini.
