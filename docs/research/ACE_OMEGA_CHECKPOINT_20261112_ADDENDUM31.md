# ACE Ω — Addendum 31, 2026-11-12: Tahap I — Penemuan Operator: Katalog Tumbuh oleh Mekanisme, Terukur

Menjawab vonis Tahap F (substrat = hafalan katalog), tahap ini
membangun mekanisme pertumbuhannya (PR #132,
`operator_discovery.py`): pencarian atas ruang **skema edit AST
generik** (konstanta int, literal string, tukar/unwrap binop,
tukar compare, ikat-ulang indeks return) pada tugas yang tak bisa
dipecahkan substrat; setiap perbaikan satu-edit yang
shown-sempurna diabstraksi menjadi operator (skema + jalur situs
struktural + transformasi relatif); operator **diakui masuk
katalog hanya bila memperbaiki ≥2 tugas pool independen**.
Batas kejujuran dinyatakan di muka: ruang skemanya dirancang
manusia; operatornya yang ditemukan mekanisme.

Dua insiden instrumen dicatat apa adanya: (1) run uji pertama
**OOM-killed oleh kandidatnya sendiri** — edit sembarang dapat
membuat BFS berputar selamanya; kini setiap evaluasi kandidat
dibatasi jam-dinding keras. (2) Run v1 menemukan **nol kandidat**
untuk returns_start_distance karena `dist[a][b]` adalah rantai
Subscript bersarang, bukan slice Tuple — bug skema, diperbaiki,
uji regresi ditambahkan, run v2 yang berlaku.

**Hasil terukur (semesta Tahap F; pool 3 tunggal/kelas; evaluasi
tidak pernah disentuh penemuan):**

| kelas baru | operator diakui | transfer evaluasi |
|---|---|---|
| dist_step_2 | int_constant di situs langkah | 0 → 3/15 |
| wall_char_x | string_literal di situs dinding | 0 → 3/15 |
| bounds_off_by_one | 3 perbaikan setara-semantik (unwrap, swap→Mult, konstanta→0) | 0 → 2/14 |
| returns_start_distance | return_indices (ikat-ulang gr, gc) | 0 → 3/15 |

Kontrol katalog: **34/34 sebelum dan sesudah** (tanpa regresi).

Skala hasil dinyatakan persis: transfer bersifat parsial —
pasangan defek dengan masking tetap gagal, konsisten dengan
pelajaran OMEGA-10. Yang terbukti bukan penguasaan kelas baru,
melainkan **pertumbuhan katalog oleh mekanisme generik dengan
kontrol penerimaan dan transfer terukur**. Untuk pertama kalinya
di program ini, katalog ACE bertambah tanpa operator tulisan
tangan per kelas.

Status gerbang tidak berubah: G1 MEASURED-DEMONSTRATED
(berkualifikasi), G2 MEASURED-nol ×2, lainnya seperti Addendum 30.
