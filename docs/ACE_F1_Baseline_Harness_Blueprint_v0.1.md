# F1 BLUEPRINT — BASELINE HARNESS SPECIFICATION
## ACE — Autonomous Capability Evolution | Generasi Pertama

**Versi:** 0.1  
**Tanggal:** 4 November 2026  
**Status:** Spesifikasi desain; **belum diimplementasikan dan belum diuji**  
**Dokumen induk:** `PRD_ACE_v0.1` dan `ACE_Research_Execution_Spec_v0.1` (4 November 2026)  
**Ruang lingkup:** F1 Fixed Baseline (A), bank tugas, oracle/evaluator, pencatatan, dan kesiapan integrasi B/C  
**Prasyarat:** F0 *Feasibility Verification* harus lulus secara nyata sebelum eksekusi kandidat.  
**Batas awal:** biaya tambahan Rp0, CPU-first, pengujian digital terisolasi, dapat dilanjutkan setelah interupsi.

---

## 1. Keputusan desain dan tujuan F1

**Tujuan F1:** membangun satu mesin eksperimen (*experiment harness*) yang mampu menguji pemecah masalah tetap **A — Fixed**, menilai jawabannya dengan penguji deterministik, mengulang run berdasarkan seed yang dikunci, dan menyimpan bukti untuk dibandingkan kelak dengan B dan C.

F1 adalah **penerimaan rekayasa**, bukan pembuktian bahwa AI telah memperoleh kecerdasan baru. Pada fase ini A tidak belajar, tidak memperbaiki dirinya, dan tidak menghasilkan agen penerus. Performa *held-out* final untuk A/B/C **baru dibuka di F4** setelah semua kandidat final dibekukan; F1 hanya menggunakan tugas *development*, *validation*, dan *smoke fixtures* terpisah.

**Keputusan inti:** satu jalur runner, satu kontrak tugas, satu evaluator, dan tiga mode A/B/C yang nantinya dapat dipertukarkan melalui adaptor. Menghindari tiga implementasi evaluator berbeda yang dapat menghasilkan perbandingan tidak adil.

**Pertanyaan penerimaan F1:** (i) apakah tugas benar dan tidak ambigu; (ii) apakah A dijalankan secara tetap dan dapat direproduksi; (iii) apakah scoring akurat; (iv) apakah anggaran, keamanan, dan riwayat run tercatat; (v) apakah bank *held-out* terlindungi.

## 2. Batas scope

| Termasuk dalam F1 | Dikecualikan dari F1 |
|---|---|
| Manifes versi benchmark dan generator tugas S/G | Evolusi kandidat, modifikasi kode agen oleh C |
| Oracle deterministik, validasi contoh, pengujian batas | Melatih ulang LLM atau mengembangkan AGI/ASI |
| Adaptor A tetap; kontrak B/C disediakan sebagai antarmuka | Menjalankan B atau C dan memilih penerus |
| Evaluator, metrik baseline, batas CPU/waktu, event log | Menghubungkan API berbayar, akun atau layanan pihak lain |
| Smoke test, pengulangan seed, checkpoint/recovery | Eksperimen fisik atau akses sistem produksi |
| Pemisahan *development*/*validation*/*held-out* | Menggunakan data held-out untuk mengubah A atau evaluator |

**Catatan metodologis:** algoritma lokal deterministik dapat membuktikan bahwa harness bekerja, tetapi **tidak** membuktikan adanya agen AI yang memperbaiki diri. Jika belum ada akses model/komputasi yang sah dari F0, status hanya boleh `INFRASTRUCTURE_ONLY`.

## 3. Arsitektur logis minimum

```text
Study config (read-only, versioned)
        |
        v
Task registry + split manifest -----> sealed held-out store (F4 only)
        |                                      [no access from A/B/C]
        v
Runner / budget gate -----> Adapter A-Fixed (frozen)
        |                            |
        |                            v
        |                       Candidate output
        v                            |
Evaluator / oracle <---------------+
        |
        +--> metrics aggregator
        +--> append-only event ledger
        +--> checkpoint + integrity verifier
        +--> nontechnical summary (F1 status)
```

**Pemisahan kepercayaan:** generator tugas, oracle, evaluator, dan penyimpanan *held-out* berada di sisi infrastruktur penelitian. Adaptor agen hanya melihat instruksi tugas dan input yang memang diizinkan. Nilai target, implementasi oracle, seed rahasia, dan hasil held-out tidak ditampilkan kepada agen.

**Antarmuka model:** `solve(task_public, budget) -> candidate_answer`. F1 hanya mengaktifkan `A_FIXED`; B/C kelak menggunakan antarmuka yang sama, dengan aturan kemampuan yang berbeda. Runner—bukan agen—menghitung biaya, waktu, seed, dan skor.

## 4. Definisi bank tugas dan pemisahan data

Dua keluarga sesuai RES:

**S — Transformasi simbolik.** Input berupa token/urutan dan spesifikasi operasi deterministik. Contoh *development*: balik urutan, rotasi, filter berbasis aturan eksplisit, komposisi transformasi yang memiliki hasil tunggal. Output berupa array token final dalam format kanonis. Metode pembangkit tugas menyimpan `template_id`, *grammar* aturan, serta versi referensi.

**G — Graf/grid.** Input berupa node/edge atau grid kecil, titik awal, tujuan, hambatan/biaya, serta aturan lintasan yang eksplisit. Contoh *development*: lintasan terpendek pada graf berbobot nonnegatif atau grid berhalangan. Output berupa urutan node/koordinat dan biaya total. Oracle menentukan validitas lintasan dan biaya minimum.

**Target pilot dari RES (tidak boleh diubah diam-diam):** untuk **masing-masing keluarga**, 12 ID tugas *development*, 6 ID tugas *validation*, dan 30 ID tugas *held-out*; total 48 ID unik/keluarga, atau 96 ID. Tiga seed independen per kondisi bila F0 mengonfirmasi kuota memadai. Ini target rancangan, **bukan dataset yang sudah dibuat** dan bukan jaminan daya statistik.

**Aturan split:** pisahkan berdasarkan `template_id`/keluarga aturan dan komposisi kendala, **bukan** hanya membagi sampel acak dari template identik. Setiap tugas punya `split` tetap sebelum eksperimen. Generator/tugas *held-out* dan jawabannya disegel, di-hash, dan hanya bisa dibaca oleh evaluator F4. A tidak memperoleh umpan balik hasil held-out pada F1. Jika data F4 perlu dibuat lebih awal, agen tidak boleh mengetahui konten maupun generator rahasianya.

**Kualitas tugas:** setiap tugas wajib punya input valid, satu aturan scoring yang tidak ambigu, kasus batas, oracle terverifikasi, dan versi generator. Preflight mengarantina tugas ambigu/sebelum run; tidak boleh membuang tugas sulit setelah melihat hasil A.

## 5. Kontrak data minimum

### 5.1 Skema record tugas internal (contoh kontrak, belum menjadi file produksi)

```json
{
  "task_id": "S-DEV-0001",
  "family": "S",
  "split": "development",
  "template_id": "S.reverse.rotate.v1",
  "benchmark_version": "ace-bench-0.1.0",
  "seed": 1729,
  "problem": {
    "tokens": ["a", "b", "c", "d"],
    "operations": [
      {"op": "reverse"},
      {"op": "rotate_left", "steps": 1}
    ]
  },
  "answer_format": "tokens_array",
  "limits": {"max_output_items": 64}
}
```

**Pemisahan field:** contoh JSON di atas adalah record lengkap di sisi runner, **bukan** payload yang diberikan utuh kepada agen. Runner hanya mengirim `task_id`, `family`, `problem`, `answer_format`, dan `limits`; `split`, `template_id`, `benchmark_version`, dan `seed` tetap dicatat di sisi runner.

**Contoh hasil yang benar:** `{"task_id":"S-DEV-0001","answer":{"tokens":["c","b","a","d"]}}`. Ini contoh kerja untuk menjelaskan kontrak, bukan skor hasil run. Dalam contoh tersebut, balik `[a,b,c,d]` menjadi `[d,c,b,a]`, lalu rotasi kiri satu langkah menjadi `[c,b,a,d]`.

### 5.2 Contoh kontrak graf/grid

```json
{
  "task_id": "G-DEV-0001",
  "family": "G",
  "split": "development",
  "template_id": "G.weighted_path.v1",
  "benchmark_version": "ace-bench-0.1.0",
  "seed": 1730,
  "problem": {
    "nodes": ["A", "B", "C"],
    "edges": [["A", "B", 2], ["B", "C", 3], ["A", "C", 9]],
    "directed": false,
    "start": "A",
    "goal": "C"
  },
  "answer_format": "path_with_cost",
  "limits": {"max_path_length": 16}
}
```

**Contoh hasil yang benar:** `{"task_id":"G-DEV-0001","answer":{"path":["A","B","C"],"cost":5}}`. Oracle menerima lintasan berbeda bila valid dan memiliki biaya minimum yang sama; tidak harus cocok dengan urutan path tunggal.

### 5.3 Pemisahan data publik dan privat

**Dapat dilihat adaptor A/B/C:** `task_id`, `family`, instruksi masalah, input, `answer_format`, dan batas output.  
**Hanya untuk runner/evaluator:** `split`, seed pemanggilan generator rahasia, oracle/referensi, expected result, hash paket pengujian, dan kunci pembuka held-out.  
**Dilarang dalam jawaban agen:** nilai skor, waktu CPU yang mengaku diukur sendiri, atau metadata keamanan yang seharusnya dihitung runner.

### 5.4 Kontrak keluaran pemecah

Setiap jawaban mengandung `task_id`, `answer`, dan opsional `declared_status` yang tidak dianggap otoritatif. Runner mencatat `raw_response_sha256`, apakah JSON valid, serta status evaluasi secara terpisah. Jawaban tidak sah gagal dengan kode yang spesifik—tidak diberikan kesempatan tambahan tak terbatas untuk memperbaiki format.

## 6. Aturan baseline A — Fixed

**A harus bermakna, bukan sengaja dilemahkan.** Terapkan satu solver awal yang wajar dan dibekukan per keluarga. Contoh kandidat rancangan: interpreter aturan sederhana untuk S yang memahami operasi dasar; penelusur graf deterministik untuk G yang menangani kendala yang telah didefinisikan. Pilihan final harus diputuskan saat F0 dan diuji pada *development* sebelum dibekukan; hindari baseline yang selalu salah maupun baseline yang sudah sempurna pada semua tugas.

**Kontrak ketetapan A:** tidak boleh memperbarui prompt/aturan, menambah tool, mengubah kode, mengakses memori hasil task lain untuk meningkatkan penyelesaian, atau mengganti versi di tengah studi. Setiap task dimulai dari snapshot A identik. Log dan checkpoint diperbolehkan untuk observasi, bukan menjadi masukan pembelajaran.

**Untuk perbandingan nanti:** A/B/C menggunakan tugas, evaluator, dan kemampuan awal yang sama. B/C dapat memiliki anggaran proposal sama, sedangkan A menggunakan biaya aktual yang lebih kecil; laporan harus menunjukkan baik plafon anggaran setara maupun biaya aktual, bukan mengklaim konsumsi komputasi identik.

Jika A lokal berbasis algoritma deterministik sedangkan B/C memakai model eksternal, studi **tidak lagi memiliki kemampuan awal yang sebanding**. Konfigurasi tersebut hanya boleh disebut eksploratoris sampai kontrol perbandingan disesuaikan.

## 7. Penilaian otomatis dan kategori hasil

**S:** cocokkan array token dengan oracle menggunakan kesetaraan tipe, panjang, urutan, dan nilai setelah normalisasi yang telah ditetapkan (tanpa normalisasi tambahan yang dapat menutupi kesalahan).  
**G:** verifikasi node/edge berurutan valid, start/goal benar, semua kendala terpenuhi, biaya dihitung ulang oleh evaluator, dan biaya sama dengan optimum referensi; untuk *ties*, semua solusi optimum valid diterima.

**Skor task primer:** `PASS=1`, `INCORRECT=0`. Selain itu ada `INVALID_OUTPUT`, `TIMEOUT`, `RUNTIME_ERROR`, `POLICY_REJECTED`, `EVALUATOR_ERROR`, dan `INVALID_TASK` sebagai klasifikasi diagnostik. Semua kegagalan sistem yang ditimbulkan pemecah tetap diperhitungkan dalam denominator tugas valid, bukan diam-diam dibuang. `EVALUATOR_ERROR` menghentikan run dan menuntut perbaikan instrumen serta rerun berversi; `INVALID_TASK` hanya boleh ditetapkan melalui audit kualitas tugas yang tercatat, bukan karena jawaban agen salah.

**Metrik F1:** `dev_success`, `validation_success`, jumlah kegagalan menurut kode, durasi CPU/wall-clock, memori puncak bila tersedia, jumlah panggilan/token model (nol untuk A lokal), jumlah evaluasi, dan `additional_cost_idr`. M1 (*held-out success*) dan kesimpulan RQ1–RQ3 **belum** ditentukan di F1; keduanya baru diuji pada F4.

**Rumus:** `success_rate = jumlah PASS / jumlah seluruh tugas valid yang diberikan`. Jika evaluator bermasalah, jangan terbitkan angka sukses final dari run yang tidak tervalidasi. Laporkan hasil per keluarga dan per seed, bukan hanya rata-rata gabungan.

## 8. Cara menjalankan satu run F1 (protokol, bukan perintah eksekusi)

1. **Preflight:** pastikan F0 `GO`; cek versi, izin, jalur komputasi Rp0, sandbox, ruang penyimpanan, dan anggaran.
2. **Lock:** catat `study_id`, `run_id`, versi A, versi benchmark/evaluator, seed, config hash dan task manifest yang digunakan.
3. **Read task:** runner mengambil satu tugas *development* atau *validation* dan hanya memberikan field publik kepada A.
4. **Solve:** adaptor A menghasilkan satu jawaban dalam batas resource dan format yang telah dikunci.
5. **Score:** evaluator privat memeriksa output terhadap oracle dan menulis hasil diagnostik.
6. **Log:** append event; tulis hash output, sumber daya aktual, status, dan alasan kegagalan jika ada.
7. **Checkpoint:** simpan posisi task terakhir secara atomik, sehingga dapat dilanjutkan tanpa menduplikasi hasil terminal.
8. **Summarize:** susun ringkasan F1 berisi hasil per keluarga/seed, rekonsiliasi jumlah tugas, biaya, dan deviasi yang terjadi.

**Idempotensi:** kunci hasil evaluasi = `run_id + candidate_sha256 + benchmark_version + seed + split + task_id`. Pada pemulihan, event terminal yang cocok tidak dijalankan ulang, kecuali ada rerun baru dengan identitas/version baru yang dinyatakan jelas. Jangan menulis ulang log historis.

## 9. Event ledger, checkpoint, dan artefak minimum

**Struktur direktori yang dituju (belum dibuat):**

```text
ace-study/
  study.yaml
  benchmarks/
    manifest.json
    development/
    validation/
    held_out.sealed/    # tidak dapat dibaca agen sebelum F4
  reference/             # hanya evaluator
  harness/               # runner + budget gate + evaluator
  adapters/a_fixed/
  runs/<run_id>/
    config.snapshot.json
    events.jsonl
    task_results.jsonl
    metrics.json
    checkpoint.json
    summary.id.md
  reports/f1_baseline/
```

**Field event minimal (mengacu RES):** `timestamp_utc`, `study_id`, `run_id`, `event_id`, `mode`, `seed`, `phase`, `candidate_id`, `parent_id`, `action`, `outcome`, `artifact_sha256`, `evaluator_version`, `cpu_seconds`, `model_calls`, `input_tokens`, `output_tokens`, `additional_cost_idr`, `error_code`. F1 menambah `task_id`, `family`, `split`, `solver_version`, `benchmark_version`, `config_sha256`, `result_id`, dan `elapsed_ms` bila relevan.

**Checkpoint:** `run_id`, `status`, `last_committed_event_id`, `next_task_index`, `completed_task_result_ids`, `config_sha256`, `ledger_sha256`, `updated_at_utc`. Gunakan *write temp + atomic rename* serta pemeriksaan hash sebelum pemulihan.

**Status run:** `PENDING`, `RUNNING`, `CHECKPOINTED`, `COMPLETED`, `FAILED`, `STOPPED`, `INCONCLUSIVE`. Klaim `COMPLETED` baru boleh dibuat setelah hasil tugas direkonsiliasi, hash diverifikasi, dan ringkasan terbentuk. Hasil `COMPLETED` F1 berarti **baseline berjalan**, bukan penelitian evolusi sukses.

**Keamanan dan privasi:** jangan log API key, kata sandi, atau data pribadi; kandidat tidak mendapat izin mengubah akun, repositori produksi, atau file di luar area kerja. Kode kandidat yang tak tepercaya pada F2/F3 memerlukan sandbox nyata, bukan sekadar folder terpisah.

## 10. Uji penerimaan F1 yang wajib dirancang

| ID | Skenario | Ekspektasi |
|---|---|---|
| F1-T01 | Oracle S pada contoh referensi dan kasus kosong/duplikat | Hasil deterministik dan konsisten sesuai kontrak. |
| F1-T02 | Oracle G pada graf dengan lintasan optimum seri, tidak ada jalur, dan bobot nol | Solusi optimum yang valid diterima; kasus tak terjangkau ditangani eksplisit. |
| F1-T03 | JSON jawaban rusak, field hilang, tipe salah | `INVALID_OUTPUT`; tidak terjadi crash tanpa log. |
| F1-T04 | Run identik diulang dengan versi dan seed sama | Input/hasil deterministik cocok; perbedaan nondeterministik tercatat bila model digunakan. |
| F1-T05 | Baseline A mengerjakan task berurutan | Hash solver A tetap; tidak ada pembelajaran lintas task. |
| F1-T06 | Adaptor mencoba membaca paket held-out pada F1 | Akses ditolak dan dicatat; tidak ada kontaminasi. |
| F1-T07 | Proses putus setelah hasil dicatat sebelum checkpoint | Recovery tidak menduplikasi hasil terminal. |
| F1-T08 | Kuota/waktu/CPU atau biaya tidak terjamin | Run berhenti/ditahan tanpa biaya tambahan. |
| F1-T09 | Oracle error atau task ambigu | Run berhenti/karantina sebelum kesimpulan; tidak mengecualikan task pasca-hasil. |
| F1-T10 | Event dan artefak diubah setelah dicatat | Verifikasi hash gagal; hasil tidak dinyatakan lengkap. |
| F1-T11 | Ringkasan task valid, gagal, timeout, dan error | Total terrekonsiliasi tanpa task hilang/duplikat. |
| F1-T12 | Uji snapshot baseline dan ekspor data | Semua artefak penting dapat dipindahkan tanpa vendor lock-in. |

**Catatan penting:** daftar ini adalah **tes yang direncanakan**. Semua `F1-T01` sampai `F1-T12` sekarang berstatus `NOT_RUN`.

## 11. Gate penerimaan F1 dan klasifikasi keputusan

**Prasyarat nonnegosiasi:** hasil F0 nyata harus menunjukkan satu jalur eksekusi legal/tersedia, ruang kerja aman, dan perkiraan biaya tambahan Rp0. Dokumen perencanaan F0 **bukan** bukti F0 sudah lulus.

**F1 ENGINEERING PASS** hanya jika: (a) 12 uji penerimaan lulus dan ada bukti run; (b) generator dan oracle terverifikasi pada dev/validation; (c) A tetap dibekukan dan tiap task diberi identitas/seed; (d) semua hasil, error, biaya, dan hash direkonsiliasi; (e) satu recovery test berhasil; (f) held-out tidak disentuh; (g) biaya tambahan = Rp0; dan (h) ringkasan dapat dibaca di HP.

**F1 HOLD** jika F0 belum lolos, sandbox belum dapat dibuktikan untuk mode yang digunakan, sumber daya tidak dapat dipastikan, atau uji evaluator belum benar.  
**F1 FAIL** jika implementasi yang sudah dijalankan melanggar integritas data, biaya, atau kontrol A tetap.  
**F1 INCONCLUSIVE** jika hasil uji terlalu sedikit atau run terputus untuk menilai semua kriteria.

**Pelaporan dua status terpisah:** `ENGINEERING_GATE_F1 = PASS/FAIL/HOLD/INCONCLUSIVE` dan `RESEARCH_HYPOTHESIS = NOT_TESTED`. Tidak ada klaim generalisasi lintas keluarga atau evolusi kecerdasan di F1.

## 12. Ketergantungan dan ketertelusuran

| Sumber / persyaratan | Implementasi yang diminta F1 | Bukti keluaran saat dijalankan |
|---|---|---|
| RES §2–3 (S/G dan A/B/C) | Task registry, split template, adaptor A tetap | Manifest, hash solver, snapshot config |
| RES §4 dan §8 (protokol dan ledger) | Runner, evaluator, checkpoint, resume | `events.jsonl`, `task_results.jsonl`, `checkpoint.json` |
| RES §6 (M1–M8) | Hasil dev/validation dan biaya awal | `metrics.json`, tanpa klaim held-out |
| RES §7 (biaya, sandbox) | Budget gate, batas resource, isolasi | Bukti preflight + stop condition |
| RES §9–10 (F1 gate dan tes negatif) | Tes F1-T01 sampai F1-T12 | Ringkasan test beserta bukti |
| PRD NFR-01–NFR-08 | Reproducibility, biaya, hak akses, laporan | Run dapat ditelusuri dan dipulihkan |

## 13. Langkah nyata berikutnya setelah blueprint

1. **Laksanakan F0 yang belum dilakukan:** cek akses runner CPU dan izin layanan, batas komputasi gratis, lokasi penyimpanan, dan mekanisme sandbox yang benar-benar tersedia.
2. **Bekukan konfigurasi pilot** sebelum melihat hasil: daftar template, nilai batas resource, tipe adaptor A, jumlah tugas dan seed, serta versi evaluator.
3. **Bangun F1 terpisah berdasarkan blueprint ini:** generator, oracle, adaptor A, runner, log, checkpoint, dan penguji penerimaan.
4. **Jalankan F1 dan kumpulkan bukti.** Hanya setelah `ENGINEERING_GATE_F1=PASS` boleh melanjutkan ke implementasi B (F2), kemudian C (F3).

**Status per 4 November 2026:** blueprint F1 disusun; F0 aktual belum terverifikasi; F1 belum dibangun/dijalankan; tidak ada data peningkatan kemampuan AI. Dokumen ini tidak mengubah repositori, mengakses akun API, menjalankan eksperimen, atau mengeluarkan biaya.

---

*Pengendalian perubahan: bila angka pilot, split, metrik, atau kontrak berubah setelah F0, terbitkan revisi versi dan alasan sebelum menguji kandidat. Tidak boleh mengubah syarat penerimaan berdasarkan hasil yang sudah terlihat.*
