# ACE Ω — Addendum 20, 2026-11-12: Amendemen Identifiabilitas OMEGA-10

Perangkap residual pilot tertutup di akarnya. PR #122 (draft,
bertumpuk di atas #121). Agenda direktur butir #3 selesai.

## Dua syarat shown yang sekarang ditegakkan generator

Pemilihan kasus shown di `curriculum_lab.py` dibangun ulang:

- **R1 identifiabilitas** — setiap perbaikan parsial (subset wajar
  mana pun dari defek yang diperbaiki) harus gagal di ≥1 kasus
  shown. Validator menegakkannya (`check_identifiability`); tugas
  yang grid-nya tidak dapat mengidentifikasi defeknya ditolak
  secara jujur saat generasi.
- **R2 jalur gradien** — harus ada urutan perbaikan satu-defek yang
  menaikkan skor shown secara ketat di setiap langkah.

## Dua formalisasi yang gugur (dicatat agar tidak diulang)

1. R1 saja tidak cukup: himpunan shown minimal yang mengidentifikasi
  bisa membuat semua langkah pertama berskor nol — greedy berhenti
  di titik yang teridentifikasi penuh namun tak terjangkau.
2. Gradien per-defek (setiap defek harus terbayar sendiri dari buggy)
  **tidak dapat dipenuhi secara prinsip** untuk pasangan pricing:
   defek pajak *menutupi* defek member (member diperbaiki di hulu
   pajak) — memperbaiki member saja tidak meluluskan satu pun kasus
   grid; hanya memperbaiki pajak dulu yang membukanya. Bentuk jalur
   adalah prasyarat pendakian yang sebenarnya.

## Verifikasi

Solver greedy substrat v2 yang persis dipakai pilot (anggaran 200)
kini menyelesaikan **15/15** tugas berbentuk residual yang
diregenerasi (member_basis+tax_basis, pricing L3) — yang dulu 0/15 —
dengan shown kecil (rata-rata 2 kasus). 19/19 test kurikulum
(termasuk 3 test identifiabilitas baru); sapuan penuh 211 test OK.

Catatan kejujuran: amendemen ini mengubah kurikulum, jadi angka
pilot v1 tidak dijalankan ulang dan tidak diubah; pilot v2 (tahap
berikutnya) akan dipra-registrasi di atas kurikulum hasil amendemen,
ditambah keluarga ketiga bergaya grid sesuai agenda direktur.
