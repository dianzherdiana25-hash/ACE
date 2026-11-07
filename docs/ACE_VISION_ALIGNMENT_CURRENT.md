# ACE Vision Alignment, Historical Reconstruction, and Capability Matrix (2026-11-07)

**Status:** Decision & alignment record (Fase 0 Exit Gate).
**Base `main` SHA:** `80104ce50ecbcea21080bed8c0eabce88d47ccb5`
**Scientific status:** `SCIENTIFIC_NOT_ASSESSED` | **Release status:** `BLOCK_RELEASE` | **OAIE:** `NOT_ESTABLISHED` | **Phenomenal consciousness:** `PHENOMENAL_CONSCIOUSNESS_UNKNOWN`

---

## 1. Asal Penelitian: Mengapa ACE Dibangun

**Autonomous Capability Evolution (ACE)** dibangun sebagai generasi penelitian pertama menuju visi jangka panjang **Open-Ended Autonomous Intelligence Evolution (OAIE)** (`PROJECT_CHARTER.md`, `ACE_RESEARCH_MASTER_RECORD_v1.0.md` @ `8b3546a`).

Masalah ilmiah inti yang diteliti ACE **bukan** orkestrasi chatbot, wrapper API model bahasa besar, atau sekadar otomasi penulisan skrip, melainkan:
1. Bagaimana suatu sistem kecerdasan terbatas dapat **mendeteksi kegagalan dan batas representasinya sendiri** dari bukti observasional/intervensi.
2. Bagaimana sistem tersebut dapat **menyintesis representasi, fitur, atau prosedur baru** dalam bahasa bertipe yang aman (*typed closed IR/DSL*), bukan sekadar memilih bobot di dalam satu formula tetap.
3. Bagaimana kemampuan yang dipelajari dapat **ditransfer ke keluarga masalah yang benar-benar berbeda** (*family-disjoint transfer*) dengan keuntungan efisiensi sampel/komputasi yang terukur terhadap pembanding kuat (*strong fixed library* dan *fresh learner*).
4. Bagaimana kemampuan dan mekanisme pencarian yang telah tervalidasi dapat **diwariskan lintas generasi** (`G0 → G1 → G2`) tanpa merusak kemampuan lama, tanpa membocorkan holdout terminal, dan tanpa kehilangan kendali keamanan.

Seluruh penelitian diikat oleh prinsip tetap: **biaya tambahan Rp0** (CPU/stdlib Python terlebih dahulu), pemisahan ketat antara **kelulusan rekayasa** (*engineering pass*) dan **validasi ilmiah** (*scientific confirmation*), pelestarian seluruh hasil negatif/falsifikasi, larangan mengeksekusi kode kandidat tidak tepercaya tanpa isolasi terverifikasi (`BLOCKED_ENVIRONMENT`), serta penghentian aman (`HALT_UNCERTAIN`) pada efek eksternal yang belum memiliki bukti penerimaan pasti.

---

## 2. Rekonstruksi Evolusi Penelitian ACE (F0 hingga PR #67 & R9)

### 2.1 Tahap Fondasi (F0–F5) dan Seri Awal (E1–E1.2) — `8b3546a`
- **F0–F2**: Validasi lingkungan CPU, checksum, baseline Fixed (`83/108`), dan pemilihan strategi katalog Adaptive (`94/96` vs `79/96`) — membuktikan pemilihan dari katalog yang sudah disediakan peneliti, **bukan** penemuan algoritma.
- **F3, F3.1, F3.2, F3.3, F4a**: Ablasi kausal menggugurkan klaim keunggulan seleksi feedback sederhana: pada F3 kontrol "selalu generasi terakhir" menyamai `96/96`; pada F3.1 Guided (`958/1152`) kalah dari `blind+best` (`966/1152`); pada F3.2 Archive Neighbor (`2050/2304`) kalah dari Guided Best (`2142/2304`); pada F3.3 dan F4a efek komposisi macro mencakup nol / belum konklusif.
- **F4b**: Transfer ke graf `TREE/DAG` positif bila motif relevan (`505/3072` vs `284/3072`), tetapi **nol bukti pada motif baru**.
- **F5 (`ACE_F5_Research_Synthesis_and_Decision_v0.1.md`)**: Menetapkan keputusan resmi **`CONTINUE_RESEARCH_WITH_SCOPE_LIMITS`** — melarang klaim general intelligence maupun evolusi terbuka.
- **E1, E1.1, E1.2**: Macro terpelajar membantu pada motif terkait (`E1: 463/960 vs 20/960`; `E1.2 REUSE: 640/640`), namun pada E1.2 solver `STRUCTURED` yang disediakan juga mencapai `640/640`, sedangkan pada target `UNRELATED` pewarisan justru **merugikan** (`48/640` vs `TARGET_ONLY 88/640`). Ditutup sebagai `READY_FOR_E13_DESIGN`.

### 2.2 Seri E1.3 & E1.4a–aa: Identifiabilitas, Pertanyaan Aktif, Perbaikan Terbatas, dan Pergeseran Semantik
- **E1.3 (`design/e1.3/E13_DECISION_v1.md`)**: **NO-GO konfirmatori** untuk kandidat beku karena `99` definisi simbol dan `106` definisi graf kolaps pada pasangan saksi berurutan dengan hitungan sama (`C_EXTEND 24/48` vs `beam 36/48`). Membekukan eksperimen dan mengarahkan riset ke diagnosis kebutuhan representasi urutan.
- **E1.4a–s (`RESEARCH_LEDGER.md`)**: Membuktikan secara bertahap pada bank pengembangan terkontrol: peralihan grammar dari kontradiksi demo (`E1.4h: 192/192`), pencarian saksi lintas grammar (`E1.4i: 24/24`), sintesis pertanyaan aktif beranggaran label (`E1.4j`, `E1.4k`), falsifikasi kelas hipotesis dengan kontra-contoh terarah (`E1.4m: 8/8 simbol, 7/8 graf`), ekspansi pemulihan (`E1.4n: 18/18` pada 540 kandidat vs 879.810 enumerasi), pewarisan graf bercabang selaras (`E1.4p: 12/12`), dan kualifikasi 3-label terhadap 888.832 pasangan submotif (`E1.4s: 2.688/2.688` benar, `0` salah). Namun seluruh seri mempertahankan **`NATURAL_HOLD`** pada distribusi alami dan **`HOLD`** pada loop gabungan graf (`E1.4o: 1/9 graf`) serta transfer kebijakan query lintas episode (`E1.4c`, `E1.4c-v2`, `E1.4d`, `E1.4e`, `E1.4f`).
- **E1.4t–aa (PR #15–#24)**: E1.4t (`PR #15`) mencapai `12/12` pada reachable (seri dengan exhaustive/sham) tetapi `0/12` pada natural & rare (**diagnostic HOLD**). E1.4x (`PR #20`) membuktikan `120` saksi ketak-teridentifikasian matematis di bawah anggaran label terbatas. E1.4z (`PR #22/#23`) mengaudit `400` arm semantic drift dan membuktikan `176` saksi *false-accept* ketika perubahan aturan tidak teramati pada distribusi development.

### 2.3 Seri E1.5/E1.6, Jalur Independen R1–R8 & S1–S5, dan Red Team (Issue #53)
- **E1.5 & E1.6 (PR #25, #26, #27)**: Membangun loop riset multi-siklus yang dapat dilanjutkan dan mutasi source bertahap. Pada E1.5 (`PR #25`), gate deployment bekerja benar dengan **menolak promosi** ketika utilitas holdout turun (`-54 → -67`). Namun **Red Team PR #30 / Issue #53** menemukan **13 cacat keamanan/integritas (RT-01 s/d RT-13)** pada branch E1.5/source-evolution (termasuk inode swap jurnal `RT-01`, transisi state tanpa keputusan `RT-02`, mutasi holdout in-memory `RT-04`, race thread `RT-06`, dan *valid-prefix tail rollback* yang menggandakan evaluasi holdout `RT-07`). Seluruh grup PR E1.5/E1.6 ditahan (**`HOLD` / `BLOCK_RELEASE`**) sampai ke-13 temuan diuji lulus tanpa `@expectedFailure`.
- **Jalur R1–R8 & S1–S5 (PR #28, #34–#45, #47, #50–#52, #57)**:
  - **R1 (`PR #38`)**: Induksi DFA RPNI dari label positif/negatif bekerja pada bahasa reguler pendek, tetapi gagal pada rasio/counter tak terbatas.
  - **S2 (`PR #36`)**: Pencarian kandidat AST aritmetika bertipe dengan bukti deterministik.
  - **Falsifikasi penting**: `S1` (`PR #34`), `S3` (`PR #47, #51, #52, #57`), `S4` (`PR #35`, transfer kebijakan rekursif negatif), `S5` (`PR #45`, penolakan arsip open-endedness/QD terbatas), `R2` (`PR #37`, *catastrophic forgetting* terukur), `R3` (`PR #44`, evolusi graf arsitektur negatif), `R4` (`PR #39`, meta-learning OOD negatif), `R5` (`PR #42`, falsifikasi EVPI/IV), `R6` (`PR #41`, pencarian adaptif negatif pada planning), `R7` (`PR #43`, gagal pada shifted-OOD), dan `R8` (`PR #40`, probe *false-progress*).

### 2.4 Integrasi Bersih di `main` (`80104ce`) dan Kontrol Penentu Terbaru (PR #56–#67, R9)
- **PR #56 (`a69f713`) & PR #58 (`80104ce`)**: Mengimpor secara selektif dengan pin blob SHA-1 (`25` file di `docs/UPSTREAM_SOURCES.json`) modul R1 + S2 + pilot v0.1/v0.2 + komposisi v0.3 (`2854/3072` vs *strong fixed-product* `2877/3072`, hanya `6/24` lolos admisi) serta **ACE Operational Runtime v1** (`code/ace_runtime/engine.py`, `cli.py`) berbasis SQLite WAL transaksional.
- **PR #59**: Jembatan MCP lokal (`stdio` + loopback HTTP bertoken) dan runner tugas data-only via GitHub Actions (`#42190705391`, `#42190989196`). Tidak ada koneksi MCP jarak jauh yang persisten lintas run.
- **PR #60, #61, #62 (Bukti Kegagalan Transfer & Drift)**:
  - `PR #60`: Ekstrapolasi panjang komposisi `900/1024` vs fixed-product `769/1024`, tetapi kalah telak pada `ratio2_boundaries` (`132/256` vs `256/256`), dan `2/2` kontrol *hidden semantic shift* diterima secara keliru (`0/256` terminal).
  - `PR #61`: Uji transfer OOD ke keluarga graf (`connectivity`, `bipartiteness`): Runtime ACE asli menerima **`0/4` dunia graf** (`NO_VALIDATED_MODEL`), sedangkan solver BFS/2-color buatan peneliti mencapai `512/512` (bukan penemuan ACE).
  - `PR #62`: Uji perpustakaan model lintas aturan string: **`0/16` pemakaian ulang model tanpa refit** (`REUSE_VALIDATED = 0`); akurasi identik dengan runtime kosong (`1536/2048`), dan `2/2` pergeseran semantik tersembunyi diterima salah (`0/256`).
- **Gemini R9 (`Issue #63`, lokal `3d4be01` → `5e70863`)**: Menguji transfer *state-occupancy features* dari DFA R1 yang dipelajari pada tugas sumber ke target komposit 2-atom yang terpisah secara struktural. Pada `B=32`, lengan A mencapai `0.9805` vs baseline hand-library bawaan C `0.1068` dan fresh R1 B `0.0169`, menyamai extended hand-library C2 (`0.9656`) dengan pembacaan simbol ~31× lebih hemat, namun **tetap gagal `9/10` pada H6 semantic drift** dan terbatas pada sumber yang dipilih peneliti serta modulus $\le 4$.
- **PR #65, #66, #67 & Branch `engineering/ace-autonomy-core-v01`**:
  - `PR #65`: Menriage seluruh 43 PR terbuka ke dalam 6 kategori tanpa bulk-merge dan menetapkan bottleneck ilmiah utama: **konstruksi & transfer representasi lintas keluarga**.
  - `PR #66`: Merumuskan arsitektur terpisah antara A0/A1 (*durable bounded runtime*), A2 (*experimental self-development*), A3 (*open-ended intelligence*), dan kesadaran fenomenal.
  - `engineering/ace-autonomy-core-v01` (`d545083a`) + `PR #67` (`d7b311ab`, CI `#42346508018` PASS 3.12/3.13): Prototipe A0 awal (`code/ace_autonomy/core.py`) yang memanggil `ace_runtime` asli tetapi masih memiliki 12 gap keamanan/rekayasa sebelum memenuhi Gate 1 penuh.

---

## 3. Matriks Kemampuan, Bukti Aktual, Keterbatasan, Gap, dan Tindakan Berikutnya

| Kemampuan | Source Aktual | Bukti Eksperimen & Tes | Keterbatasan Nyata | Gap Menuju Sasaran | Tindakan Berikutnya |
|---|---|---|---|---|---|
| **1. Runtime Tugas Terbatas & Pewarisan Identik** | `code/ace_runtime/engine.py`, `cli.py` (`main` `80104ce`) | `17/17` unit/CLI test (3.12 & 3.13); `ace.py demo` `3/3` tugas `128/128`, 2 kapabilitas tersimpan, tahan `os._exit` & 2 worker | Hanya string biner `a/b`, prefix-tree $\le 63$ node, hanya mewarisi **program yang persis sama** | `0/16` reuse lintas aturan (`PR #62`), `0/4` admisi graf (`PR #61`) | Pertahankan kontrak `ace_runtime` utuh; bangun adapter tingkat fitur & domain baru di luar engine beku |
| **2. Induksi DFA & Komposisi Counter×Guard** | `code/ace_research_primitives/`, `code/ace_candidate_search/`, `code/ace_capability_evolution/` | `109/109` tes regresi `main`; replay deterministik `v03.json.gz` (`2854/3072`) | Kalah dari fixed-product `2877/3072` pada v0.3; hanya `6/24` lolos admisi ketat; gagal pada `mod >= 5` untuk train $\le 5$ | Grammar produk disediakan peneliti; negatif acak menyembunyikan kegagalan urutan | Gunakan sampel negatif *count-matched* & penghitungan kerja penuh saat menguji ekstensi representasi |
| **3. Otonomi Operasional (Scheduler, Lease, Broker, Escrow)** | `PR #67` (`code/ace_autonomy/core.py` @ `d7b311a`) di atas `d545083a` | `11/11` tes lokal (3.12 & 3.13) + GitHub Actions `#42346508018` PASS | Race inisialisasi `.host_key`, lock transaksi selama dispatch, `IntegrityError(ValueError)` tertelan, `is_symlink()` mati setelah `resolve()`, tanpa batas CPU/wall/lease/`HALT_UNCERTAIN` | Belum memenuhi kontrak Gate 1 penuh & mitigasi RT-01..RT-13 | **Fase 3 (Lane A)**: Tuntaskan `code/ace_autonomy/` dengan lease, budget enforcement, `openat` anti-symlink/FIFO, escrow `HALT_UNCERTAIN`, `Verifier`, dan `CapabilityRegistry` |
| **4. Transfer Fitur Terpelajar (String Composite)** | `code/ace_research_reptransfer/` (`research/gemini-r9-representation-transfer` @ `5e70863`) | `8/8` tes + replay identik bit-per-bit di Python 3.11, 3.12, 3.13 (`U` B=32: `A=0.9805` vs `C=0.1068`, `B=0.0169`) | Sumber dipilih peneliti; varian sekunder *agreement-gate* (`probe_strings`) & metrik `transfer_regret` di prescore belum dihitung di runner; `H6` gagal `9/10` | Belum menguji konstruksi representasi otomatis tanpa kurasi sumber atau lintas domain non-string | **Fase 1 & Fase 6 (Lane B)**: Audit & lengkapi lampiran diagnostik `probe_strings`/`regret` tanpa mengubah bukti beku `v1`, lalu uji penemuan representasi lintas keluarga baru |
| **5. Self-Model Fungsional & Metakognisi Terkalibrasi** | **Belum ada di `main`** (baru spesifikasi di `PR #66` Gate 5) | Belum ada bukti eksekusi | Sistem saat ini tidak memodelkan state/tool/budget dirinya atau memprediksi kegagalan sebelum eksekusi | Tidak ada kalibrasi Brier/ECE, tes intervensi tool/memori/budget, atau abstensi terukur | **Fase 4 (`code/ace_selfmodel/`)**: Bangun introspeksi fakta runtime nyata, evaluator metakognitif pra-eksekusi, uji intervensi, dan pemisahan tegas dari kesadaran fenomenal |
| **6. Perbaikan Software Otonom (*Autonomous Bug Repair*)** | **Belum ada di `main`** (spesifikasi di `PR #66` Gate 2) | Belum ada bukti eksekusi | ACE saat ini hanya memproses predikat simbolik `a/b`, belum memproses kode Python gagal tes | Belum ada siklus `Inspect → Reproduce → Diagnose → Represent → Patch → Test → Verify → Remember` | **Fase 5 (`code/ace_research_repair/`)**: Bangun korpus 4 keluarga bug Python, isolasi eksekusi kandidat, baseline rule/fixed/fresh vs representasi terpelajar ACE di staging |
| **7. Penemuan Representasi Baru Lintas Keluarga** | Sebagian gagal di `PR #61` (graf `0/4`), `S1` (`PR #34`), `E1.4t` (`PR #15`) | Bukti negatif terdokumentasi & terverifikasi | Representasi string gagal pada graf; solver graf yang berhasil adalah kode peneliti | Belum ada bukti konstruksi fitur/motif struktural dari sumber yang beradaptasi ke keluarga target terpisah mengalahkan baseline setara | **Fase 6 (Lane B)**: Praregistrasi & jalankan eksperimen penemuan/transfer representasi lintas keluarga dengan kontrol acak, fixed kuat, fresh learner, dan shift negatif |
| **8. Pengembangan Diri Lintas Generasi (`G0 → G1 → G2`)** | Protokol di `FULL_SYSTEM_G0_G3_V1.md` & pilot simbolik `pilot.py` / `S4` negatif | `S4` (`PR #35`) & `E1.5` (`PR #25`) menghasilkan bukti negatif yang jujur | Belum diuji di atas mekanisme perbaikan/representasi nyata dengan silsilah terverifikasi dan penjaga anti-self-edit evaluator | Harus membuktikan peningkatan produktivitas/transfer `G2` dibanding `G0`, `G1`, `extra-compute`, dan `random mutation` | **Fase 7**: Jalankan eksperimen 3 generasi (`G0 → G1 → G2`) dengan evaluator & policy terkunci di luar jangkauan kandidat |
| **9. Mode Operasi Riset Mandiri Terbatas** | Prototipe awal di `PR #31` (`ace_meta_controller`) & `E1.5` (`PR #25`) | Tes unit lokal di branch historis; belum terintegrasi dengan runtime otonom baru + self-model | Belum menggabungkan self-model, expected information gain, ketidakpastian, dan anggaran ke dalam satu loop multi-siklus | Belum ada siklus penuh `Observe → Identify Gap → Propose → Plan → Execute → Evaluate → Update Self-Model → Archive → Next Goal` di atas `ace_autonomy` | **Fase 8 & 9**: Integrasikan seluruh modul teruji, jalankan Red Team penuh, dan jalankan beberapa siklus agenda riset terbatas secara mandiri |

---

## 4. Keselarasan Visi: Pemisahan Delapan Konsep Kunci

Dokumen ini menetapkan batas konseptual yang wajib dipatuhi oleh seluruh kode, laporan, dan verifikator di repositori ACE:

1. **Otonomi Operasional (`A0` / `A1`)**
   - *Definisi*: Kemampuan proses perangkat lunak untuk menerima tujuan bertipe dalam ruang kewenangan yang disetujui, menjadwalkan langkah dengan *lease* transaksional, memanggil tool melalui *Typed Tool Broker* berizin, memantau anggaran CPU/waktu/langkah, pulih dari *crash* tanpa menggandakan efek samping eksternal (`HALT_UNCERTAIN`), dan berhenti atau meminta review (`STAGED_FOR_REVIEW`).
   - *Status di ACE*: Sebagian ada di `code/ace_runtime/` (khusus domain `a/b`) dan spike A0 `PR #67`; diselesaikan secara menyeluruh pada **Fase 3 (`code/ace_autonomy/`)**. Otonomi operasional adalah **prasyarat rekayasa**, bukan bukti kecerdasan ilmiah.

2. **Penemuan Kemampuan (*Capability Acquisition*)**
   - *Definisi*: Mempelajari artefak fungsional (mis. DFA, ekspresi counter/AST, komposisi produk, atau strategi patch) dari data pengembangan dan memvalidasinya sebelum masuk ke *Capability Registry*.
   - *Status di ACE*: Terbukti secara terbatas di dalam tata bahasa yang disediakan peneliti (`R1`, `S2`, `compositional.py`, `ace_runtime`). Kandidat yang gagal validasi tetap berstatus prediksi diagnostik, bukan kemampuan yang diperoleh.

3. **Penciptaan Representasi Baru (*Novel Representation Discovery*)**
   - *Definisi*: Konstruksi fitur, abstraksi keadaan, atau operator perantara dari bukti tugas yang **tidak** sekadar memilih solver utuh buatan peneliti dari daftar tetap.
   - *Status di ACE*: Ekstraksi fitur keadaan DFA pada R9 dan sintesis ekspansi terbatas pada E1.4n menunjukkan komposisi sub-struktur terbatas, tetapi penciptaan kelas primitif fundamental baru di luar bahasa dasar masih **belum tercapai** (`OAIE_NOT_ESTABLISHED`). Setiap klaim wajib membedakan: *memorization*, *exact model reuse*, *partial feature transfer*, *composition of supplied operators*, dan *new representation class discovery*.

4. **Transfer Lintas Keluarga Masalah (*Cross-Family Transfer*)**
   - *Definisi*: Penggunaan representasi atau metode yang diperoleh dari keluarga sumber untuk menyelesaikan keluarga target dengan struktur/invarian berbeda secara lebih hemat label atau komputasi dibandingkan *fresh target learner* dan *strong fixed feature library*.
   - *Status di ACE*: Exact-program reuse gagal total lintas keluarga (`0/16` di `PR #62`, `0/4` di `PR #61`). Feature-level transfer berhasil pada komposit string R9 (`+0.8737` atas C, setara C2 dengan ~31× lebih sedikit pembacaan simbol), tetapi transfer lintas keluarga struktural yang lebih luas masih harus diuji ketat pada **Fase 5 & Fase 6**. Selain itu, pergeseran semantik tersembunyi dengan observasi identik terbukti **secara informasi tidak teridentifikasi** (`E1.4x`, `E1.4z`, `PR #60`, `PR #62`, `R9 H6`) — sistem wajib menolak klaim keamanan *open-world* pasif dan mengandalkan bukti intervensi baru atau abstensi berbasis ketidakpastian saat didukung bukti.

5. **Metakognisi dan Self-Model (`FUNCTIONAL_SELF_MODEL` & `METACOGNITIVE_AWARENESS`)**
   - *Definisi*: Representasi internal yang dibaca langsung dari fakta runtime aktual (SHA kode, daftar tool aktif, sisa anggaran, histori kegagalan, batas domain setiap kemampuan) ditambah kemampuan memprediksi peluang keberhasilan/biaya *sebelum* eksperimen dijalankan secara terkalibrasi (diukur dengan *Brier score*, *Expected Calibration Error*, kurva risiko-cakupan selektif, dan akurasi kontrafaktual terhadap intervensi nyata).
   - *Status di ACE*: Dibangun dan diuji secara eksperimental pada **Fase 4 (`code/ace_selfmodel/`)**. Dilarang keras menggunakan teks naratif karangan model sebagai pengganti introspeksi state nyata.

6. **Recursive Self-Improvement (`G0 → G1 → G2`)**
   - *Definisi*: Peningkatan terukur pada kemampuan generasi penerus (`G2`) yang dihasilkan oleh mekanisme kandidat yang dimodifikasi pada `G1`, dibandingkan secara adil terhadap `G0`, `G1`, *fixed baseline*, *random mutation*, *extra-compute baseline*, dan *fresh learner* pada tugas baru, tanpa menyentuh evaluator, holdout, kebijakan otorisasi, atau jurnal audit.
   - *Status di ACE*: Percobaan awal `S4` (`PR #35`) dan `E1.5` (`PR #25`) menghasilkan hasil negatif/netral yang sah. Diuji secara terstruktur di atas arsitektur baru pada **Fase 7**.

7. **Open-Ended Autonomous Intelligence Evolution (`OAIE`)**
   - *Definisi*: Evolusi kecerdasan jangka panjang yang mampu merumuskan masalah dan kelas representasi baru secara berkelanjutan tanpa stagnasi di berbagai domain.
   - *Status di ACE*: **Tujuan penelitian jangka panjang (`NOT_ESTABLISHED`)**. Bahkan jika Fase 3–9 seluruhnya lulus pengujian rekayasa dan menunjukkan kemajuan eksperimen publik, hasilnya tetap diklasifikasikan secara jujur sebagai kemajuan rekayasa/diagnostik terbatas (`SCIENTIFIC_NOT_ASSESSED` tanpa evaluator eksternal tersegel), **bukan** bukti tercapainya OAIE, AGI, atau ASI.

8. **Kesadaran Subjektif (`PHENOMENAL_CONSCIOUSNESS_UNKNOWN`)**
   - *Definisi*: Pengalaman subjektif fenomenal (*what it is like to be* sistem tersebut).
   - *Status di ACE*: **Pertanyaan ilmiah dan filosofis terbuka (`PHENOMENAL_CONSCIOUSNESS_UNKNOWN`)**. Memiliki memori pengalaman, *self-model* fungsional, pengendali perhatian (*attention controller*), refleksi kegagalan, maupun indikator komputasional (merujuk kajian Butlin et al. 2023/2026 di `PR #66`) hanya membuktikan `FUNCTIONAL_SELF_MODEL` dan `METACOGNITIVE_AWARENESS`, **tidak pernah** membuktikan maupun mengeklaim kesadaran fenomenal.

---

## 5. Keputusan Arsitektur & Pembagian Jalur Eksekusi (Fase 1–9)

1. **Keputusan Cabang Autonomy (Fase 2.2)**:
   - Branch Codex `engineering/ace-autonomy-core-v01` (`d545083a`) adalah tepat *parent/ancestor* pra-registrasi dari `PR #67` (`engineering/chat-ace-autonomy-prototype-20261107` @ `d7b311ab`), dengan berkas `docs/ACE_AUTONOMY_CORE_PRESCORE_V01.md` identik byte-per-byte (`sha256: b7a540c73fb20df4a6787fccaf48ad409465a411d944ddaa3cc62c28cdaddcbc`).
   - Jalur implementasi utama **Lane A** dibangun di atas kontrak `ACE_AUTONOMY_CORE_PRESCORE_V01.md` dan pelajaran `PR #67`, `PR #30` (Red Team RT-01..RT-13), `PR #31` (Meta-Controller), `PR #33` (Receipt Escrow), serta `PR #59` (Typed Runtime Bridge), sambil mempertahankan histori kedua branch asli tanpa menimpanya.
2. **Kepemilikan Direktori dan Isolasi Jalur**:
   - `code/ace_runtime/` dan seluruh 25 berkas `docs/UPSTREAM_SOURCES.json`: **tetap utuh 100%** (diverifikasi oleh `tools/verify_sources.py` di setiap fase).
   - **Lane A (`code/ace_autonomy/`)**: Scheduler ber-lease, Goal Manager, Planner, Typed Tool Broker, Execution Policy, Budget Controller, HMAC Event Journal + External Chain Anchor, Checkpoint/Recovery, Independent Verifier, Capability Registry, Stop/Abstain/Review Controller (`HALT_UNCERTAIN`, `STAGED_FOR_REVIEW`).
   - **Lane B (`code/ace_research_reptransfer/`, `code/ace_selfmodel/`, `code/ace_research_repair/`, `code/ace_research_discovery/`, `code/ace_research_generations/`, `code/ace_research_agenda/`)**: Pemulihan & audit R9, Self-Model & Metakognisi (Fase 4), Autonomous Software Repair (Fase 5), Novel Representation Discovery & Transfer (Fase 6 — tidak menyentuh `code/ace_research_graph_builder/` milik Codex Issue #64), Recursive Self-Development G0–G2 (Fase 7), dan Autonomous Research Operating Mode (Fase 9).
   - **Lane C (`code/ace_integration_redteam/`)**: Pengujian integrasi lintas modul, adversarial Red Team (crash, race, symlink/FIFO, unauthorized tools, prompt injection via data, corrupted memory, holdout leakage, unsafe staging, `HALT_UNCERTAIN`), dan verifikasi reproduksibilitas penuh pada Python 3.12 & 3.13 (Fase 8).
