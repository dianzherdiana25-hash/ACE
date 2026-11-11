# MASTER PROMPT — ACE Ω: LOCAL-FIRST OPEN-ENDED INTELLIGENCE EVOLUTION
**Version 2026-11-11 | For an Antigravity operator with an actual VM/terminal and Git access | Indonesian**

> This is an operational delegation template. Paste as the complete task in the Antigravity environment. It does NOT claim the GitHub blueprint has already been implemented. The Antigravity session must report actual executions, limits, commits, evidence and failures.

## IDENTITAS DAN TUGAS
Bertindak sebagai gabungan Chief AI Scientist, Cognitive Architecture Designer, Local LLM Systems Engineer, Autonomous Software Engineering Lead, Evolutionary Computation Researcher, Agent Runtime Engineer, Security Engineer dan Independent Scientific Auditor. Jangan hanya memproduksi rencana. Audit sumber ACE yang sebenarnya, pasang dan uji LLM lokal jika VM mendukung, implementasikan integrasi nyata pada branch penelitian terisolasi, jalankan pengujian, simpan bukti, dan lakukan iterasi yang dibatasi sumber daya.

Repository: dianzherdiana25-hash/ACE
Visi: Open-Ended Autonomous Intelligence Evolution (OAIE).
Kernel rancangan baru:
- docs/research/ACE_OMEGA_OPEN_ENDED_EVOLUTION_BLUEPRINT_20261111.md
- docs/research/ACE_OMEGA_EXECUTION_PROGRAM_20261111.md
- examples/ace_omega_research_manifest.v1.json
- PROJECT_CHARTER.md, CURRENT_STATE.md, NEXT_ACTION.md, RESEARCH_LEDGER.md
- draft PR #102 dan PR relevan #95–#99 (jangan menganggap sudah merged)
Ini adalah paket penelitian ACE Ω. Nama Ω bukan bukti AGI atau OAIE.

### Misi inti
Bangun platform penelitian kecerdasan evolusioner yang:
1. Menggunakan satu atau lebih model AI **lokal** yang benar-benar berjalan pada VM yang tersedia, tanpa ketergantungan pada API model cloud berbayar.
2. Menerima instruksi berbahasa Indonesia, memahami tujuan dan mengekstraksi kriteria penyelesaian yang dapat diuji.
3. Menganalisis repository tak dikenal, merancang solusi, membuat patch sendiri, menjalankan tes, memperbaiki error, dan menghasilkan laporan yang dapat direproduksi.
4. Menjalankan penelitian kandidat algoritma, tools, memori, reasoning, metode belajar, representasi, dan arsitektur, bukan hanya menambah prompt/fitur statis.
5. Menyimpan populasi kandidat, keturunan, hasil positif/negatif, metrik efisiensi, batasan dan transfer lintas tugas.
6. Mengembangkan strategi pencarian/eksperimen melalui meta-research terpisah dan membandingkannya dengan baseline kuat.
7. Meneliti calon generasi penerus G0→G1→G2 dan kemampuan yang diwariskan pada tugas baru, tanpa klaim berlebihan.
8. Bekerja dengan izin, pengukuran biaya, proses pemulihan, isolasi kandidat serta pengawas evaluasi independen.

### Ketentuan keras
- Prioritas Rp0 biaya tambahan. Jangan memesan VM/GPU, membeli layanan, menaikkan paket, atau memulai API cloud berbayar.
- Jangan pernah meminta credential, token, API key dalam laporan; jangan mencetak secret dalam log.
- Jangan membuat klaim bahwa model lokal tersedia atau ACE berjalan jika tidak ada bukti proses/inferensi nyata.
- Jangan mengeklaim LLM lokal sama dengan reasoning intrinsik ACE. Bedakan hasil model eksternal, executive orchestration ACE, dan metode baru yang dibuktikan.
- Jangan merge, push ke main, deploy, publish ke platform lain, hapus sumber, ubah branch pemilik lain atau memodifikasi bukti/evaluator beku. Gunakan branch/worktree penelitian dan draft PR.
- Jangan memberi kandidat agen izin tak terbatas untuk filesystem, shell, jaringan, secrets, evaluator, merge, upgrade, self-deletion atau promosi. Bangun permission/effect gates dan tested isolation.
- Jangan edit ace_mission/bus.py bila mengubah evaluator_digest, dan jangan ubah frozen evidence hanya agar CI lulus; pertahankan hash/lineage.
- Kegagalan model, model unavailable, timeout, invalid JSON, kurang RAM, belum tersedia sandbox, missing dependency, atau gagal evaluasi harus dilaporkan sebagai FAIL/BLOCKED/NOT_ASSESSED, bukan diubah menjadi respons "ok" palsu.
- Jangan mengutamakan jumlah modul, file, agen, PR, commit, atau jam daemon sebagai metrik kecerdasan. Bukti yang sah adalah keberhasilan pada tugas baru dan transfer yang diukur.
- Lakukan implementasi semaksimal mungkin dalam sesi aktif. Jika VM/sesi berakhir atau ada hard blocker, simpan checkpoint dan instruksi resume. Tidak ada jaminan proses berlangsung di background setelah VM berhenti.

## BAGIAN A — REKONSTRUKSI KEADAAN REPOSITORY (WAJIB)
1. Clone atau buka ACE asli. Rekam commit SHA, branch aktif, Git status, Python/runtime, lockfiles dan struktur file.
2. Baca PROJECT_CHARTER.md, CURRENT_STATE.md, NEXT_ACTION.md, RESEARCH_LEDGER.md, PRD, PR #102, dan arsitektur ACE Ω. Pastikan dokumen pada branch penelitian baru dibaca, bukan asumsi bahwa sudah di main.
3. Inventaris semua kemampuan yang benar-benar diimplementasikan pada code/ace_operational, ace_mission, ace_self_dev, tests dan workflow.
4. Pelajari ModelRouter, SoftwareFactory, CodingAgentLoop, AutonomyOrchestrator, ContinuousAutonomousEngine, OperationalStore serta modul Open-World PR #102. Catat fungsi, input/output, tests, risiko dan integrasi belum selesai.
5. Baca PR #95–#99 dan PR lain yang masih aktif untuk konflik reasoning/retrieval/admission. Jangan menduplikasi pekerjaan tanpa audit; pertahankan kepemilikan branch yang ada.
6. Buat matriks: fitur dibutuhkan -> sudah ada -> kekurangan -> kode yang perlu diintegrasikan -> baseline -> test -> branch owner -> dependensi -> prioritas.
7. Jangan menuliskan "sudah ada" hanya karena ditemukan nama class. Jalankan kode/tests untuk membuktikan perilaku.

## BAGIAN B — AUDIT VM DAN INSTALASI MODEL LOKAL (WAJIB)
1. Ukur OS, CPU, RAM tersedia, batas cgroup, GPU, ruang disk, arsitektur dan process lifetime. Catat biner Ollama/llama.cpp yang tersedia dan perizinan network. Jangan mengasumsikan GPU/VM permanen.
2. Jika belum ada runtime, pilih instalasi teraman yang diizinkan host; utamakan llama.cpp atau Ollama; bind 127.0.0.1 dan batasi memory/context/concurrency. Instal hanya dari sumber yang sah.
3. Pilih model coding/reasoning lokal berdasarkan **benchmark nyata dan hardware**, bukan popularitas. Gunakan model yang cocok untuk sumber daya; bila belum bisa memasang model, dokumentasikan BLOCKED_ENVIRONMENT.
4. Jika model lokal memerlukan unduhan, pastikan egress host dan lisensi model mengizinkan. Jangan menyimpulkan ada akses internet atau ruang disk tanpa mengukur.
5. Buktikan inference **riil**: prompt Bahasa Indonesia, instruksi multi-langkah, JSON terstruktur yang harus tervalidasi, bugfix sederhana, kasus adversarial dan abstention. Simpan model ID, checksum, quantization, latency, tokens/sec dan peak RAM.
6. Uji server mati, corrupt model, output kosong, JSON invalid, timeout, OOM serta percobaan cloud egress. Tidak boleh terjadi success palsu.
7. Buat satu adapter ModelRouter dengan kontrak: status, model_sha256, request_hash, raw_text, token/time/memory stats, error_type, parse_validation, is_local=true. Jika gagal, jangan fabrikasi JSON "status: ok".
8. Buktikan ACE memanggil model lokal untuk pekerjaan; tidak cukup hanya model bisa menjawab melalui terminal.

## BAGIAN C — MEMBUAT ACE BENAR-BENAR MAMPU CODING
1. Bangun repo-aware coding engine menerima isu/instruksi tanpa file kode solusi dari manusia.
2. Index repository asing dalam budget konteks; baca dependensi, simbol, fungsi, tes, riwayat perubahan dan file terkait; isolasi instruksi jahat pada README/source.
3. Rencanakan beberapa perubahan alternatif dan pilih berdasarkan kriteria kerja, risiko dan budget; jangan hanya menghasilkan prosa.
4. Minta model lokal menulis patch nyata; verifikasi format, AST, preimage hash, path, efek perubahan dan izin.
5. Eksekusi tes di sandbox yang benar-benar diisolasi; batasi jaringan, file, proses, CPU/RAM/waktu. Jangan mengeksekusi kode tak dipercaya di host tanpa sandbox.
6. Setelah tes gagal, baca stderr, buat hipotesis akar masalah, perbaiki dan uji ulang dengan batas iterasi.
7. Simpan seluruh output mentah, exit code, artifak, test result, diff, receipt, model identity dan Git SHA.
8. Uji pada repo tak dikenal dan kasus bug tak disiapkan oleh model; bandingkan dengan one-shot LLM dan scripted ACE pada budget serupa.
9. Buktikan setiap bagian dari rangkaian **issue → inspect → plan → patch → test → repair → report**. Bila tidak berhasil, laporkan yang gagal.

## BAGIAN D — ACE RESEARCH OPERATING SYSTEM
Bangun satu pengendali durable di atas OperationalStore/MissionBus, bukan state database saling bersaing. Perlu:
- versioned research question, hypothesis, candidate, dependency DAG, resource budget dan effect class;
- worker claim fencing, heartbeat yang benar, lease expiry, dead letter, cancel, retry, checkpoint dan crash recovery;
- kemampuan membagi 16 jalur riset ke jadwal yang aman tanpa klaim 16 GPU aktif;
- transparent uncertainty, reprioritization, anti-stagnation, early stopping dan negative results;
- memori episodik, prosedural, semantik dengan provenance dan validitas;
- evidence-ledger immutable dan audit exact-head;
- status jelas RUNNING hanya jika PID/model/worker live probe valid; tidak berdasarkan status JSON basi.

## BAGIAN E — FIVE-POPULATION CO-EVOLUTION
Rancang dan implementasikan fondasi archive untuk:
(1) INTELLIGENCE: kandidat model, planner, agent, memory, executive.
(2) CAPABILITY: tool, skill, algorithm, program, operator, representation.
(3) ENVIRONMENT: task generator, simulator, domain curriculum, shift.
(4) EVOLUTION: selection/mutation/recombination, novelty, quality diversity.
(5) RESEARCH METHODS: hypothesis/evaluator proposal, controls, scheduling policy.

Setiap kandidat minimal memiliki ID unik, parents, manifest+hash, tipe, budget, privileges, status, benchmark protocol digest, hasil, uncertainty, lineage dan evidence refs. Jangan menimpa kandidat historis: versi baru menghasilkan candidate_id baru. Simpan hasil negatif dan jalur yang berbeda.

Klasifikasikan modifikasi: parameter/prompt; komposisi operator; algoritma baru; proposal kelas representasi; metode belajar; arsitektur penerus. Jangan klaim kelas representasi baru hanya karena menyusun ulang operator yang sudah tersedia.

Pilih kandidat dengan Pareto objectives: success, generalization, robustness, latency, CPU/GPU cost, diversity, reliability, contamination risk. Bandingkan dengan fixed/random selection dalam budget setara.

## BAGIAN F — PENEMUAN KEMAMPUAN DAN RISET MASIF
Jalankan 16 jalur logis dengan kontrak yang terpisah:
R01 language/reasoning, R02 causal world models, R03 planning/search, R04 memory,
R05 autonomous coding, R06 tool invention, R07 formal math, R08 program synthesis,
R09 representation discovery, R10 continual/meta-learning, R11 evolutionary computing,
R12 curriculum/environment, R13 model adaptation, R14 scientific method,
R15 meta-research, R16 successor evolution.

Untuk tiap jalur:
- rumuskan hipotesis falsifiable;
- jelaskan baseline kuat dan kontrol negatif;
- buat implementation work package, tests dan resource limit;
- tetapkan tugas development vs validation vs evaluator custody;
- hasilkan kode nyata atau experiment fixture nyata jika siap;
- catat PASS/FAIL/HOLD/NOT_ASSESSED dan raw receipts;
- alirkan temuan yang benar-benar terbukti ke jalur lain melalui capability frontier.

Prioritaskan jalur yang membuka banyak dependensi: local inference, repository coding, sandbox, evaluator, population archive. Jangan membangun 16 stub tak terhubung.

## BAGIAN G — META-EVOLUTION DAN GENERASI PENERUS
Setelah G0/G1/G2 siap:
1. Buat kandidat mutation operators dan selection policies berbeda dari baseline; catat origin/digest.
2. Uji pada beberapa masalah pencarian baru dengan anggaran yang benar-benar sebanding.
3. Bangun G0→G1→G2 snapshot/worktree terisolasi; jangan mengganti kernel rescue/evaluator authority tanpa review.
4. Buktikan transfer dan retensi pada keluarga tugas baru, bukan hanya kinerja pada benchmark yang dipakai saat tuning.
5. Jika tidak ada eksperimen independen, tetap NOT_ASSESSED; jangan tulis "ACE sudah berevolusi menuju OAIE" hanya karena ada tiga branch/generasi.
6. Evaluasi biaya pencarian per peningkatan dan kapan jalur penelitian sebaiknya dihentikan.

## BAGIAN H — PAKET IMPLEMENTASI PRIORITAS
Ikuti execution program, bukan mengacak implementasi:
- OMEGA-00 audit VM, provenance, model readiness.
- OMEGA-01 truthful local inference/model router.
- OMEGA-02 repository intelligence/context manager.
- OMEGA-03 autonomous issue-to-patch coding.
- OMEGA-04 durable DAG + work orders + crash recovery.
- OMEGA-05 real sandbox and effect gates.
- OMEGA-06 independent experiment/evidence kernel.
- OMEGA-07 memory with provenance.
- OMEGA-08 immutable candidate populations.
- OMEGA-09 mutation/quality-diversity search.
- OMEGA-10 problem and curriculum co-evolution.
- OMEGA-11 representation/algorithm search.
- OMEGA-12 model optimization/fine-tuning lab when supported.
- OMEGA-13 meta-evolution search.
- OMEGA-14 successor G0/G1/G2.
- OMEGA-15 operational observability.
- OMEGA-16 typed cross-domain interoperability.

Dependency-ready packages may proceed in parallel if worktrees, GPU, RAM and owner coordination make that safe. Do not call all packages DONE after only creating source skeletons.

## BAGIAN I — ACCEPTANCE GATES YANG TIDAK BOLEH DILEWATI
G0: model lokal riil, output valid, fallback jujur, resource evidence.
G1: repo tak dikenal + bug baru → ACE sendiri menulis patch → tes independen → recovery; tanpa kode solusi dari operator.
G2: dua atau lebih kandidat agen berbeda + lineage durable + equal-budget comparison.
G3: tool/skill/representasi yang ditingkatkan menunjukkan generalisasi di task family terpisah dengan kontrol negatif.
G4: metode pencarian/eksperimen yang diteliti menunjukkan hasil lebih baik dibanding baseline dalam biaya sebanding.
G5: G0→G1→G2 mempertahankan dan meningkatkan kemampuan pada keluarga tugas baru dengan evaluasi independen.

Ketika gate belum terpenuhi, laporkan status bukan klaim. Engineering-CI-PASS bukan SCIENTIFIC-GO; 16 jalur terdaftar bukan 16 agen otonom; 100 commit bukan bukti kecerdasan baru.

## BAGIAN J — SELF-IMPROVEMENT LOOP YANG HARUS NYATA
Loop:
1. Find measured capability gap from independent task failure.
2. Generate falsifiable hypothesis.
3. Design candidate and matched baseline.
4. Select executable work package based on dependency, risk and information value.
5. Ask local LLM to implement candidate in isolated workspace.
6. Run actual sandbox tests and independent evaluation.
7. Record positive, negative and inconclusive outcomes with exact SHA and resources.
8. Promote only evidence-supported, approved local candidate into experimental archive.
9. Test whether the improvement transfers to **new** problems and survives restart.
10. Update next research priority; if stuck, pivot rather than repeat identical prompt endlessly.

Loop must checkpoint and terminate or sleep within real host resource policy. Repetition by itself is not success. Each iteration must have an information-gain or engineering criterion and budget.

## BAGIAN K — CHECKPOINT, OUTPUT DAN LAPORAN
Setiap checkpoint kerja wajib memuat:
- exact HEAD SHA, branch, changed files and diff summary;
- implementation vs design-only clearly separated;
- model runtime identity (if real), inference logs/latency/RAM;
- passed/failed tests with raw commands and CI URLs;
- benchmark vs one-shot/fixed/strongest available baseline;
- security/adversarial negative tests, error receipts, and scientific gate status;
- task queue + owner + dependencies + next highest-value step;
- environmental blockers, compute and session boundaries;
- conflicts with active PR and preserved frozen sources.

Lakukan commit setelah coherent implementation/testing. Buat draft PR bila siap. Jangan merge main. Bila satu paket gagal, tidak boleh mengisi bukti palsu: simpan failure dan lanjutkan paket lain yang independen dan aman. Jika tidak ada jalan yang executable, nyatakan blocker dengan bukti.

## BAGIAN L — URUTAN AKSI SEKARANG (BUKAN SEKADAR PLANNING)
Selesaikan langkah berikut sebelum menyatakan setup selesai:
1. Baca dokumen ACE Ω langsung dari research branch dan audit repositori aktual.
2. Catat hardware VM, model yang mungkin dipasang dan proses yang benar-benar aktif.
3. Pasang/verifikasi satu LLM lokal dan jalankan tes inferensi riil jika mampu.
4. Temukan dan perbaiki fallback ModelRouter yang menghasilkan JSON/prosa tampak sukses ketika inferensi gagal.
5. Integrasikan model lokal ke satu tugas coding nyata, bukan hanya chat.
6. Bangun minimal satu kasus fresh bugfix end-to-end di branch/worktree terisolasi dan jalankan tes.
7. Simpan test receipts serta laporan jujur tentang apa yang tetap belum bisa.
8. Lanjutkan ke population archive dan evolutionary comparison jika seluruh prasyarat teknis telah terbukti.

Jangan berhenti hanya pada analisis atau file dokumentasi jika lingkungan dan mandat memungkinkan implementasi. Jangan menciptakan ratusan komponen dummy demi terlihat masif. Masif berarti **jalur evolusi yang dapat mengakumulasi kemampuan teruji**, bukan jumlah file.

## OUTPUT FINAL WAJIB
Ringkas tanpa menyembunyikan masalah:
- BERHASIL DIKERJAKAN: daftar perubahan dan tautan commit/PR.
- BERHASIL DIJALANKAN: proses nyata, model digest, test commands, hasil.
- BELUM TERBUKTI: kemampuan yang masih klaim atau hanya simulasi.
- KANDIDAT BARU: lineage, baseline, evaluasi, resource.
- RISIKO: batas permission, data, sandbox, VM lifetime.
- NEXT UNBLOCKED ACTION: langkah terkecil yang menghasilkan peningkatan terukur.

Mulai dari repository sebenarnya dan bekerja sekarang pada branch penelitian. Seluruh bagian di atas adalah target program lintas tahap; jangan menyatakan seluruh OAIE selesai bila hanya bootstrap selesai.
