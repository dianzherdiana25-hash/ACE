# PRODUK DIREKTUR — KERANGKA DERIVASI SLOT EVO 0007

- Brain-of-origin: groq/openai/gpt-oss-120b
- Dihasilkan: 2026-11-18 12:09 WIB oleh hub (ila) lewat connector custom.groq
- Prompt: ~/workspace/rancangan-otak-kuat/prompt_siklus_0007_derivasi.txt
- Usage: prompt 1968 token, completion 3045 token, completion_time 6.31 s ≈ 482 t/s
- Status: produk direktur, BELUM disaring — cek aset wajib terhadap repo sebelum dikutip/dipakai (aturan berdiri dari siklus pertama).

---

**KERANGKA DERIVASI SLOT‑KOSONG EVO 0007**  
*Catatan: semua nilai **tidak** di‑isi di sini. Hanya dijabarkan cara‑cara penurunan nilai setelah vonis EVO 0006 diterima.*

---

## Slot 1: **Organ Pendistilasi — Validator vs Coder**
- **Fungsi slot**: Menentukan pasangan organ heterogen (validator ↔ coder) yang akan memproses *pattern_distilled* pada tiap episode; memengaruhi cara‑cara `approach` dan `pitfalls` dicatat dalam store pola.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – Vonis menunjukkan bahwa semua empat lengan berhasil melewati gerbang ≥ 75 % dan accept‑rate POLA memenuhi syarat. Maka pasangan organ dapat diturunkan dari konfigurasi yang terbukti stabil pada EVO 0006 (mis. validator = `v2.1`, coder = `c3.0`).  
  - **NULL (lengan sama)** – Jika vonis melaporkan tidak ada perbedaan accept‑rate antara lengan, maka organ pendistilasi dapat disamakan dengan konfigurasi *baseline* yang dipakai pada EVO 0005 (mis. `validator_default` ↔ `coder_default`).  
  - **NOT_DELIVERED** – Lengan gagal gerbang → tidak ada data pengukuran yang dapat dipakai. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: jalankan satu episode probe pada lengan POLA dengan organ dummy (mis. `validator_stub` ↔ `coder_stub`) hanya untuk memperoleh status delivery.  
  - **INSTRUMEN_TIDAK_CUKUP** – Probe < 8 → statistik organ tidak dapat di‑estimasikan. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan 2‑3 probe ekstra pada lengan POLA dengan organ yang sama, cukup untuk mencapai batas 8.  
- **Risiko bila diisi dari selera**: Memilih pasangan organ yang tidak ter‑verifikasi dapat menurunkan kualitas `pattern_distilled`, menghasilkan pola yang bias atau tidak dapat direkonstruksi.

---

## Slot 2: **Panjang Maksimum Pola (Cap Token/Karakter)**
- **Fungsi slot**: Membatasi ukuran token/karakter maksimum yang dapat tersimpan dalam setiap record `pattern_distilled`; melindungi store pola dari overflow dan menjaga konsistensi lintas‑lengan.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – Vonis memberikan nilai *margin* yang valid (mis. 45‑75 % skor). Panjang maksimum dapat dipilih dari rentang yang terbukti tidak menurunkan accept‑rate pada EVO 0006 (mis. 1024 token).  
  - **NULL (lengan sama)** – Karena tidak ada perbedaan performa, gunakan nilai *default* yang dipakai pada EVO 0005 (mis. 768 token).  
  - **NOT_DELIVERED** – Tanpa data delivery tidak ada informasi tentang beban memori tiap lengan. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: jalankan satu episode probe dengan pola‑dummy berukuran berbeda (mis. 512 → 2048) untuk mengamati efek pada delivery.  
  - **INSTRUMEN_TIDAK_CUKUP** – Kurang probe → tidak ada distribusi panjang pola. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan 4 probe pola mini pada lengan SHAM untuk mengumpulkan statistik panjang.  
- **Risiko bila diisi dari selera**: Nilai terlalu kecil dapat memotong informasi penting; nilai terlalu besar dapat memicu kegagalan storage atau menurunkan kecepatan proses.

---

## Slot 3: **Pita Margin (Mean Skor Judge atas 2 Lari Kalibrasi Kondisi Kosong)**
- **Fungsi slot**: Menetapkan rentang nilai skor judge (mis. `[bawah, atas]`) yang menjadi ambang untuk mengklasifikasikan episode‑probe sebagai *acceptable* pada fase NULL vs SUPPORTED.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – Vonis melaporkan bahwa kedua lari kalibrasi menghasilkan skor dalam kisaran yang stabil (mis. 45‑75). Gunakan rentang tersebut secara literal.  
  - **NULL (lengan sama)** – Jika skor tidak membedakan lengan, pakai rentang *neutral* yang dipakai pada EVO 0005 (mis. 50‑70).  
  - **NOT_DELIVERED** – Tanpa data delivery tidak ada skor yang terrekam. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: lakukan dua lari kalibrasi cepat pada kondisi kosong dengan probe standar untuk mengumpulkan skor.  
  - **INSTRUMEN_TIDAK_CUKUP** – Probe < 8 → tidak ada cukup observasi skor. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambah 3 probe kosong pada lengan POLA untuk mencapai minimum.  
- **Risiko bila diisi dari selera**: Rentang yang tidak mencerminkan realitas dapat mengklasifikasikan episode secara keliru, menurunkan akurasi accept‑rate.

---

## Slot 4: **N Probe Minimum untuk Vonis**
- **Fungsi slot**: Menetapkan jumlah minimum probe yang harus berhasil (delivery ≥ 75 %) sebelum vonis dapat dikeluarkan; menghindari keputusan prematur pada data terbatas.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – EVO 0006 berhasil dengan N ≥ 8; turunkan nilai slot ke **8** (atau nilai yang tercatat pada log vonis).  
  - **NULL (lengan sama)** – Vonis menunjukkan tidak ada perbedaan; nilai N dapat di‑set ke **nilai default EVO 0005** (biasanya 6) karena tidak ada kebutuhan ekstra.  
  - **NOT_DELIVERED** – Karena gerbang gagal, tidak ada N yang dapat diverifikasi. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan probe hingga total tercapai 8 pada lengan POLA, hanya untuk menguji delivery.  
  - **INSTRUMEN_TIDAK_CUKUP** – Probe kurang dari 8 langsung men-trigger vonis ini; **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan probe minimal 2 untuk mencapai ambang 8.  
- **Risiko bila diisi dari selera**: Menetapkan N terlalu rendah meningkatkan risiko false‑positive vonis; terlalu tinggi dapat menunda rilis tanpa alasan.

---

## Slot 5: **Sumber Kandidat Probe + SHA**
- **Fungsi slot**: Menentukan korpus sumber (rumah atau lanjutan) serta hash SHA‑256 yang men‑pin versi korpus yang akan dipakai pada semua lengan; memastikan reproducibility.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – Vonis menyertakan identifikasi korpus yang berhasil (mis. `corpus_home_v2` dengan SHA `a1b2c3…`). Turunkan slot ke nilai tersebut.  
  - **NULL (lengan sama)** – Jika tidak ada perbedaan performa, gunakan korpus *baseline* yang dipakai pada EVO 0005 (mis. `corpus_v1` dengan SHA `deadbeef…`).  
  - **NOT_DELIVERED** – Tanpa delivery tidak ada korpus yang terbukti; **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: jalankan satu probe minimal dengan korpus baseline untuk menguji delivery dan mengidentifikasi SHA.  
  - **INSTRUMEN_TIDAK_CUKUP** – Karena probe kurang, belum ada SHA yang diverifikasi. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan 3 probe dengan korpus candidate yang paling mungkin (mis. `corpus_home_v2`).  
- **Risiko bila diisi dari selera**: Menggunakan korpus yang belum diverifikasi dapat menimbulkan perbedaan distribusi konteks antar lengan, mengacaukan perbandingan accept‑rate.

---

## Slot 6: **Ambang Kemiripan Recall**
- **Fungsi slot**: Menetapkan threshold (mis. cosine similarity atau Jaccard) yang dipakai untuk menilai apakah konteks yang di‑recall dari `pattern_distilled` cukup mirip dengan episode‑target; memengaruhi keputusan SUPPORTED vs NULL.
- **Aturan derivasi per vonis**  
  - **SUPPORTED** – Vonis melaporkan nilai recall yang konsisten di atas ambang (mis. 0.78). Turunkan ambang ke nilai **just‑below** performa terendah yang tercatat (mis. 0.75).  
  - **NULL (lengan sama)** – Jika recall tidak membedakan lengan, gunakan ambang *netral* yang dipakai pada EVO 0005 (mis. 0.70).  
  - **NOT_DELIVERED** – Tanpa delivery tidak ada metrik recall; **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: lakukan satu episode probe dengan query recall pada lengan POLA, catat similarity.  
  - **INSTRUMEN_TIDAK_CUKUP** – Kurang probe → tidak ada data recall. **Tidak dapat menurunkan** nilai slot. *Pengukuran tambahan termurah*: tambahkan 2 probe recall pada lengan SHAM untuk memperoleh nilai minimal.  
- **Risiko bila diisi dari selera**: Ambang yang terlalu tinggi dapat menolak episode yang sebenarnya sah; terlalu rendah dapat mengakui episode yang tidak relevan, menurunkan kualitas evaluasi.

---

### Ringkasan
Setiap slot di atas menunggu **vonis EVO 0006** untuk memberikan data kuantitatif yang sah. Jika vonis menghasilkan **SUPPORTED** atau **NULL**, nilai dapat diturunkan secara langsung dari hasil pengukuran. Jika vonis **NOT_DELIVERED** atau **INSTRUMEN_TIDAK_CUKUP**, slot **tidak dapat** diturunkan dan memerlukan **pengukuran tambahan** (biasanya penambahan probe minimal pada lengan POLA atau SHAM) yang paling ekonomis. Mengisi slot secara arbitrer menimbulkan risiko **bias**, **over‑run storage**, atau **keputusan vonis yang tidak dapat dipertanggungjawabkan**.
