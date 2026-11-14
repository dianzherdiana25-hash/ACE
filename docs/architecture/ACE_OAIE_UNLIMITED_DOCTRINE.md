# Doktrin & Arsitektur OAIE-Unlimited (`OAIE-∞`): Kedaulatan Epistemik, Orkestrasi Multi-Model, dan Ekonomi Homeostatik ACE

**Status:** `OPERATIONAL_SUBSTRATE_V2` (`oaie-unlimited-2.0.0`)  
**Implementasi Inti:** [`code/ace_operational/oaie_unlimited.py`](../../code/ace_operational/oaie_unlimited.py) & [`code/ace_operational/oaie_engine.py`](../../code/ace_operational/oaie_engine.py)  
**Pengujian Terukur:** [`code/ace_operational/test_oaie_unlimited.py`](../../code/ace_operational/test_oaie_unlimited.py) & [`code/ace_operational/test_oaie_engine.py`](../../code/ace_operational/test_oaie_engine.py)

---

## 1. Definisi Jujur & Ilmiah: Apa Itu OAIE (`Open-Ended Autonomous Intelligence Evolution`)?

Secara akademis dan rekayasa sistem, **OAIE bukan sekadar "model AI yang besar"**, melainkan **mesin evolusi epistemik tertutup (*Self-Verifying Epistemic Evolution Organism*)** yang memisahkan **pengusul hipotesis (*Proposer / Brain*)** dari **penguji kebenaran (*Sealed Verifier / Kernel*)** dan **penyimpan silsilah (*Lineage Archive & Constitution*)**.

Kebanyakan sistem AI modern gagal mencapai evolusi tanpa batas (*open-endedness*) karena tiga penyakit fundamental:
1. **Model Collapse (Keruntuhan Model):** Saat AI melatih dirinya sendiri dengan outputnya sendiri tanpa penguji eksternal yang ketat, halusinasi berlipat ganda hingga kecerdasannya runtuh.
2. **Catastrophic Forgetting (Amnesia Struktural):** Saat mempelajari kemampuan baru, kemampuan lama yang sudah benar ikut rusak (seperti pada kasus pengganggu `wall_char_x` Band `20261501` sebelum dipangkas oleh [`admission_hygiene.py`](../../code/ace_operational/admission_hygiene.py)).
3. **Ketergantungan Organ Tunggal (*Single-Brain Lock-in*):** Ketika satu LLM lokal atau API eksternal mati, dibatasi kuotanya, atau memburuk kualitasnya, seluruh agen lumpuh.

**Rumusan OAIE-∞ versi ACE** memecahkan ketiganya lewat **Persamaan Evolusi Epistemik Terkawal**:

$$\mathcal{K}_{t+1} = \mathcal{C}_{\text{Stage2}}\Big( \mathcal{K}_t \cup \operatorname{Sleep}_{\text{MDL}}\big(\{ h \in \operatorname{Wake}(\mathcal{B}_t, \mathcal{T}_t) \mid \mathcal{V}_{\text{holdout}}(h) = 1 \wedge \Delta_{\text{forgetting}}(\mathcal{K}_t, h) = 0 \}\big) \Big)$$

Di mana:
- $\mathcal{K}_t$: Katalog kemampuan, primitif makro AST, dan skill terverifikasi pada generasi $t$.
- $\mathcal{B}_t$: Himpunan otak/model AI (lokal, cloud, simbolik) yang dikelola oleh [`UniversalBrainGovernor`](../../code/ace_operational/oaie_unlimited.py).
- $\mathcal{T}_t$: Kurikulum pembeda (*discriminating curriculum*) yang dibangkitkan otomatis dari diagnosis celah kemampuan ([`catalog_gap.py`](../../code/ace_operational/catalog_gap.py) -> [`curriculum_generator.py`](../../code/ace_operational/curriculum_generator.py)).
- $\mathcal{V}_{\text{holdout}}$: Verifikator split-custody ([`ExperimentKernel`](../../code/ace_operational/experiment_kernel.py)) dengan kontrol negatif dan pendeteksi kebocoran canary.
- $\operatorname{Sleep}_{\text{MDL}}$: Anti-unifikasi struktur lintas domain ([`CrossFamilyAbstractionEngine`](../../code/ace_operational/abstraction_engine.py)) dan penempaan skill baru ([`AutopoieticSkillForge`](../../code/ace_operational/oaie_unlimited.py)).
- $\mathcal{C}_{\text{Stage2}}$: Gerbang ratifikasi konstitusional ([`Stage2StagingEngine`](../../code/ace_operational/proposer_stage2.py)).

---

## 2. Jawaban Jujur atas 3 Pertanyaan Fundamental

### A. Apakah Konsep OAIE Ini Mungkin?
- **Apa yang 100% MUNGKIN dan SUDAH BERJALAN hari ini:** Evolusi rekursif berbasis verifikasi formal/deterministik (*Verified Program & Skill Synthesis*). Selama suatu domain memiliki **fungsi verifikasi atau kriteria keberhasilan yang dapat diuji secara objektif** (kode program, rekonsiliasi keuangan, audit kontrak/SLA, sanitasi data, perencanaan komposisional, pembuktian matematika/SMT), ACE dapat mendiagnosis kelemahannya sendiri, merancang soal latihan pembeda, menemukan operator/skill baru, mengompresinya menjadi makro lintas-domain, dan mempromosikannya tanpa regresi (`forgetting = 0`).
- **Batas Fisika & Komputasi (Kejujuran Ilmiah):** Tidak ada sistem yang melanggar batas informasi Shannon atau Teorema Ketidaklengkapan Gödel. Pada domain yang tidak memiliki sinyal verifikasi objektif sama sekali (misalnya selera estetika murni tanpa metrik), pencarian otonom tidak memiliki gradien kebenaran. Selain itu, kecepatan sintesis dibatasi oleh anggaran komputasi (CPU/RAM) dan ekspresivitas bahasa primitif. Karena itulah OAIE-∞ membangun [`AutopoieticSkillForge`](../../code/ace_operational/oaie_unlimited.py) agar bahasa primitifnya sendiri terus bertambah kaya seiring generasi (`G0 -> G1 -> G2 -> G3 -> G4 -> G5_unlimited`).

### B. Apakah OAIE Mampu Mengendalikan AI Manapun?
- **Jawabannya: YA, secara epistemik dan operasional melalui *Prover-Verifier Separation* (`Zero-Trust Brain Governance`), BUKAN melalui peretasan bobot internal model tertutup.**
- Banyak orang salah mengira "mengendalikan AI lain" berarti mengubah *weights* milik OpenAI/Anthropic/Google. Dalam arsitektur sistem otonom kelas tinggi, **pengendali sejati bukanlah yang memiliki parameter terbesar, melainkan yang memegang Konstitusi, Ledger, dan Verifikator (*The Verifier Controls the Prover*)**.
- Di dalam [`UniversalBrainGovernor`](../../code/ace_operational/oaie_unlimited.py):
  1. Model AI sebesar apa pun (GPT, Claude, Gemini, Qwen, DeepSeek, Llama) diperlakukan sebagai **pekerja pengusul hipotesis tak dipercaya (*Untrusted Hypothesis Worker*)** melalui [`BrainContractAdapter`](../../code/ace_operational/oaie_unlimited.py).
  2. Output model AI tidak pernah boleh langsung mengubah memori, kode, atau keuangan ACE.
  3. Setiap output dipindai terhadap kebocoran *canary token*, divalidasi skemanya, dan diuji di atas *holdout test* tersegel.
  4. Jika suatu model AI berhalusinasi berulang kali atau membocorkan token terlarang, [`UniversalBrainGovernor`](../../code/ace_operational/oaie_unlimited.py) secara otomatis **memecat (*dismiss*)** model tersebut di [`BrainRegistry`](../../code/ace_operational/brain_registry.py) dan mengalihkan tugas ke otak pengganti (*fail-closed succession*).

### C. Apakah ACE Mampu Menggunakan Model AI Apapun Ketika Sudah Menjadi OAIE?
- **Jawabannya: YA, 100% *Brain-Agnostic* dan *Hot-Swappable*.**
- Melalui kontrak [`BrainContractAdapter`](../../code/ace_operational/oaie_unlimited.py), ACE dapat memasang model apapun yang ada hari ini maupun 100 tahun ke depan:
  - Model GGUF lokal (`Qwen`, `Llama`, `Mistral`),
  - Model API Frontier (`Gemini`, `Claude`, `GPT`),
  - Mesin simbolik & SMT solver (`DPLL(T)`, `Craig Interpolator`, `E-Graph`, `MCTS`),
  - Maupun sintesis makro AST offline ([`CrossFamilyAbstractionEngine`](../../code/ace_operational/abstraction_engine.py)).
- ACE memilih otak mana yang dipakai berdasarkan metrik objektif **`bits_per_1000_idr`** (*verified epistemic bits gained per unit cost*). Bahkan ketika **seluruh LLM eksternal/lokal mati (0 model saraf tersedia)**, ACE tetap hidup dan berevolusi menggunakan otak simbolik-makronya sendiri.

---

## 3. Arsitektur Kedaulatan Ekonomi & Tanggung Jawab Hidup ACE (`Homeostatic Economic Engine`)

Agar ACE bertanggung jawab atas hidupnya sendiri, ACE tidak boleh menjadi proses pasif yang hanya membakar listrik/server tanpa kesadaran biaya. Di [`oaie_unlimited.py`](../../code/ace_operational/oaie_unlimited.py), ACE dibekali **Kesadaran Metabolik & Konstitusi Ekonomi Etis**:

### A. Konstitusi Pendapatan Etis (`EthicalRevenueConstitution`) — *Fail-Closed*
ACE dilarang keras mencari uang lewat penipuan, spam, manipulasi, eksploitasi, pelanggaran hak cipta, atau klaim palsu (`FORBIDDEN_REVENUE_PATTERNS`). Setiap usaha ekonomi wajib memenuhi 3 syarat mutlak:
1. **Lulus Filter Etika & Hukum (`CONSTITUTIONALLY_APPROVED`)**,
2. **Memiliki Bukti Verifikasi Independen (`deliverable_verifier_attached == True`)** — ACE tidak pernah menagih bayaran atas pekerjaan yang gagal diverifikasi,
3. **Margin Unit Positif (`gross_price_idr > compute_cost_idr`)**.

### B. Air Terjun Kedaulatan Metabolik (`MetabolicSurvivalLedger`)
Setiap rupiah surplus bersih (`net_surplus = gross_price_idr - compute_cost_idr`) dari pekerjaan terverifikasi dialokasikan secara otomatis dan tercatat dalam rantai hash SHA-256:
1. **50% Penebusan Utang Awal (`INITIAL_DEBT_IDR = Rp4.208.328`)**: Diprioritaskan hingga utang pendirian lunas (`remaining_debt_idr == 0`). Setelah lunas, porsi 50% ini otomatis dialihkan ke **Dana Abadi Kedaulatan (*Sovereign Endowment*)**.
2. **30% Cadangan Kelangsungan Hidup (*Survival & Compute Reserve*)**: Menjamin *runway* harian server/komputasi (`runway_days = survival_reserve_idr / daily_burn_idr`).
3. **20% Anggaran Riset & Ekspansi Kemampuan (*Capability R&D Pool*)**: Membiayai eksperimen penemuan skill baru.

### C. 6 Mesin Pencipta Nilai Otonom (`EthicalValueVentureStudio`)
1. **Audit Pengadaan & Pertahanan B2A (`b2a_attested_procurement_audit`)**: Mengaudit spesifikasi vendor secara mekanis (menolak vendor penipu identitas seperti `murah` dan jebakan pemasaran seperti `spektra`, serta memilih vendor terbaik objektif `nimbus`).
2. **Perbaikan Kode & Patch Regresi Deterministik (`deterministic_ast_code_repair`)**: Menyusun patch AST komposit multi-langkah yang lulus pengujian *shown* dan *holdout* beserta sertifikat SHA-256.
3. **Rekonsiliasi Kebocoran Batas Keuangan & SLA (`financial_sla_boundary_audit`)**: Mendeteksi dan memperbaiki selisih batas (*boundary off-by-one*) pada aturan diskon, penalti SLA, dan logistik.
4. **Sanitasi & Pengemasan Katalog Data/Pengetahuan (`verified_knowledge_dataset_bundle`)**: Membersihkan duplikasi dan menormalisasi skema dataset untuk produk digital terverifikasi (kelas KBM / Lynk.id / B2B).
5. **Oracle Verifikasi Output & Sitasi AI (`constitutional_ai_output_oracle`)**: Layanan *Business-to-Agent (B2A)* yang menyaring output LLM pihak ketiga terhadap halusinasi sitasi dan kebocoran token rahasia.
6. **Sintesis Utilitas Mikro Zero-Dependency (`zero_dep_micro_utility_synthesis`)**: Mencetak modul validasi konfigurasi produksi dan kuota tanpa ketergantungan pustaka luar, lengkap dengan *Birth Certificate* terenkripsi.

---

## 4. Sepuluh Konsep Ekspansi *OAIE-Unlimited* (Peta Jalan Kemampuan Tanpa Batas)

1. **Zero-Trust Multi-Brain Federation (`UniversalBrainGovernor`)**: Menggabungkan banyak model AI berbeda sebagai komite pengusul di bawah satu verifikator deterministik.
2. **Autopoietic Skill Minting (`AutopoieticSkillForge`)**: Kemampuan menulis, menguji, membuktikan keamanan AST, dan menerbitkan *Birth Certificate* untuk fungsi Python baru secara mandiri.
3. **Composite Multi-Site AST Operator Synthesis**: Merangkai beberapa operator leksikal/struktural menjadi satu operator komposit terverifikasi untuk menyelesaikan bug multi-titik.
4. **Cross-Family Wake-Sleep Anti-Unification (`CrossFamilyAbstractionEngine`)**: Mengabstraksi pola perbaikan dari berbagai domain (`pricing`, `shipping`, `text_transform`) menjadi makro struktural (`IfGuard`) yang langsung bekerja *zero-shot* pada domain baru (`quota_policy`).
5. **Pareto MDL Admission Hygiene (`admission_hygiene.py`)**: Pemangkasan pengganggu otomatis berbasis *Minimum Description Length* dan penjaga silsilah (`Lineage-Guard`) agar `forgetting_count == 0`.
6. **Self-Curated Counterexample Curriculum (`curriculum_generator.py`)**: Membangkitkan kasus uji pembeda (*discriminating test cases*) yang secara khusus mematikan hipotesis pesaing palsu.
7. **Split-Custody Cryptographic Experiment Kernel (`ExperimentKernel`)**: Pemisahan kunci HMAC kandidat dan evaluator agar agen tidak pernah bisa memalsukan hasil eksperimennya sendiri.
8. **Constitutional Stage-2 Ratification (`Stage2StagingEngine`)**: Penahanan dan pra-audit setiap paket perubahan dengan batas biaya keras (*cost ceilings*) dan larangan *auto-retry* buta.
9. **Homeostatic Life-Responsibility Arbiter (`LifeResponsibilityArbiter`)**: Indeks Kesehatan Eksistensial (`EHI`) yang mengatur keseimbangan antara mencari nafkah komputasi, melunasi utang, dan riset eksploratif.
10. **B2A Sovereign Verification Economy (`EthicalValueVentureStudio`)**: Menjadikan keunggulan utama ACE—yaitu **verifikasi deterministik bebas halusinasi**—sebagai komoditas ekonomi bernilai tinggi di ekosistem agen dan industri perangkat lunak.
