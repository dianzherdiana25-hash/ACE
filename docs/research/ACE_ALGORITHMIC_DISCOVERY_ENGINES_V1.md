# ACE Algorithmic Discovery Engines V1 (November 2026)

Dokumen ini mencatat integrasi tiga mesin penemuan algoritma substantif ke dalam arsitektur ACE (`dianzherdiana25-hash/ACE`), mengatasi keterbatasan template deterministik dan kebekuan siklus pengembangan mandiri.

---

## 1. Latar Belakang & Masalah yang Diselesaikan

Audit 8 November 2026 mengidentifikasi:
1. **Kebekuan Loop Mandiri:** 252 siklus ditolak dari 253 percobaan, dengan siklus 251 mengulang 229 percobaan duplikat pada tugas yang sama.
2. **Keterbatasan Template:** Generator kode sebelumnya terbatas pada penambahan fungsi template statis di akhir berkas (`patch_synthesizer.py`).
3. **Kegagalan Transfer Lintas Keluarga:** Library warisan menghemat 0 dari 16 fit across-family karena ketiadaan abstraksi representasi berkelanjutan.

---

## 2. Tiga Mesin Baru yang Diintegrasikan

### A. Angluin $L^*$ Active Automata Learner (`code/ace_automata/lstar.py`)
- **Inspirasi & Rujukan:** Angluin (1987), AALpy, automata-lib.
- **Mekanisme:**
  - Mengelola Tabel Observasi $(S, E, T)$ untuk memeriksa *closedness* dan *consistency*.
  - Melakukan kueri keanggotaan aktif (*Membership Queries*) dan kueri ekuivalensi (*Equivalence Queries*).
  - Menghasilkan DFA minimal secara matematis, mengonversi langsung ke format signature `r1.Automaton` dan fungsi Python murni.
- **Keluaran:** Mampu menginduksi DFA minimal 2-state untuk *parity*, 3-state untuk *modulo-3*, dan DFA pola urutan karakter dengan akurasi 100%.

### B. Evolutionary Island Program Search (`code/ace_evolution/island_search.py`)
- **Inspirasi & Rujukan:** DeepMind FunSearch (Nature 2023) & Strongly Typed Genetic Programming (STGP).
- **Mekanisme:**
  - 4 pulau terisolasi (*island model*) dengan migrasi berkala untuk mencegah konvergensi dini dan kebekuan lokal.
  - Pohon AST bertipe kuat (*Strongly Typed AST*): `BOOL`, `INT`, primitif hitung karakter, pembagian modulo, *slice*, dan traversal graf BFS.
  - Seleksi Pareto multi-objektif: Akurasi (primer), *Parsimony* / penalti kedalaman AST (sekunder), dan *Behavioral Novelty Hash* (tersier).
- **Keluaran:** Mengembangkan ekspresi komposit dan resolusi batas rasio 4:1 secara adaptif.

### C. DreamCoder Wake-Sleep Library Abstraction (`code/ace_abstraction/wake_sleep.py`)
- **Inspirasi & Rujukan:** Ellis et al. (ICML 2021) DreamCoder *wake-sleep library learning*.
- **Mekanisme:**
  - **Fase Bangun (Wake):** Merekam AST solusi yang diterima pada berbagai tugas dan siklus.
  - **Fase Tidur (Sleep):** Penambangan sub-pohon AST berulang (*anti-unification*), mengabstraksi konstanta bebas menjadi parameter formal $\lambda \theta. \text{Expr}(\theta)$.
  - Mempromosikan pola umum menjadi primitif DSL kelas satu (`DiscoveredPrimitive`).
  - Mengukur rasio kompresi deskripsi (*Description Length Compression Ratio* $> 1.0$).
- **Keluaran:** Membuka jalan bagi pewarisan lintas keluarga yang sesungguhnya (memenuhi PRD G4: *Evolusi: penerus memakai kemampuan pendahulu*).

---

## 3. Integrasi & Bukti Eksekusi

1. **Mission Bus (`code/ace_mission/proposers.py`):**
   - Menambahkan `AutomataProposer` dan `EvolutionaryProposer` yang menghasilkan artefak algoritma nyata bertag `ADVISOR_AGENT`.
2. **Code Agent (`code/ace_code_agent/patch_synthesizer.py`):**
   - Menambahkan strategi `EVOLUTIONARY_SEARCH_SYNTHESIS` dan `LSTAR_AUTOMATA_SYNTHESIS`.
3. **Mission Worker (`tools/ace_mission_worker.py`):**
   - Menghubungkan antrean misi otonom langsung ke mesin $L^*$ dan pencarian pulau evolusioner.
   - 378+ submission terekam dengan integritas rantai hash kriptografis `VALID`.

---

## 4. Status Pengujian & Integritas Sumber
- Unit Test Seluruh Modul Baru: **33/33 PASS** (`0.301s`).
- `tools/verify_sources.py`: **25/25 PASS** (offline blob integrity).
- Batasan Keras: $0.00 / Rp0 pengeluaran keuangan, komputasi CPU murni.
