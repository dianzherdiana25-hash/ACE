# Preregistrasi: admission Mission Bus dan reasoning internal

Tanggal 10 November 2026. Basis persis PR #95: `01916ad375aebd81aaa6d027a4f4d682a0e2cde8`.
Branch milik pekerjaan ini: `audit/ace-reasoning-admission-20261110`.
Ownership: `code/ace_mission` admission/bus/schema, `tools/ace_mission_worker.py`,
tes dan workflow khusus, dokumen/bukti baru `mission_admission`. Jangan mengubah
reasoning backend, sumber pin, evaluator independen, bank atau bukti historis.

## Hipotesis yang dapat dibantah

- H1 rekayasa: tidak ada submission baru yang memperoleh `ACCEPTED` dari keputusan
  pemanggil, metadata provider, hash, teks keberhasilan, atau source Python saja.
- H2 integrasi: kandidat JSON dalam IR xy tertutup milik reasoning lama bisa
  memperoleh paling tinggi `STAGED_EMPIRICAL` hanya setelah Mission Bus memutar
  ulang kandidat aktual pada seluruh train dan validation milik misi, dengan
  kecocokan nilai DAN tipe. Program/masalah/budget/source evaluator terikat receipt.
- H3 negatif: perubahan program, problem binding, tipe, grammar, label validation,
  source payload, receipt palsu dan batas resource tidak boleh lolos staging.
- H4 retensi: receipt, keputusan aktual, keputusan yang diminta dan hash chain
  tetap dapat dibaca setelah objek/proses dibuka ulang; state historis tidak
  ditulis ulang. Ini bukan ketahanan terhadap penyerang yang dapat mengedit DB.

## Rancangan terkunci sebelum implementasi/scoring

Gunakan lagi `Problem`, `decode_program`, `Meter`, `predict`, dan sintesis lama;
tidak ada eval/exec/import source kandidat, model, provider atau dependensi baru.
Problem terstruktur harus berada di spesifikasi misi SEBELUM submission. Artifact
JSON hanya schema, problem digest dan program; receipt yang dikirim pemanggil
tidak diterima. Bus menghitung ulang bukti dari bytes artifact yang dihash.

Penerimaan development tidak menguji novelty, OOD, baseline superiority, atau
scientific GO. Sebelum evaluator authority terpisah tersedia, `ACCEPTED` tidak
dapat diterbitkan oleh jalur ini. Python/template mission tetap
`PENDING_EVALUATION` atau `REJECTED`; hilangkan klaim angka yang tidak diukur.

## Baseline, data dan anggaran

1. Reproduksi tes lama dan benchmark reasoning publik tanpa mengubahnya.
2. Strong fresh solver pembanding tetap backend yang sama dengan anggaran sama;
   hasil PR #95 sebelumnya 552/576 tidak dipakai memilih/menyetel kandidat baru.
3. Diagnostic admission: 8 aturan × 3 seed publik dari protokol PR #95. Sintesis
   hanya menerima train/validation, bekukan program sebelum terminal. Putar ulang
   program melalui bus, score terminal hanya sesudah keputusan final. Laporkan
   coverage positif bersama penolakan negatif; always-abstain menolak semua tetapi
   mempunyai coverage nol. Jangan menyebut canary ini penemuan kemampuan baru.
4. Tiap solve maksimum 300.000 primitive, 5.000 kandidat, 5 detik. Tiap evaluasi
   bus maksimum 300.000 primitive, 5 detik, 128 observasi, 64 KiB artifact,
   depth/node/type limits dari backend. Budget evaluasi terpisah dan dibukukan;
   bukan sertifikat total biaya seluruh hidup misi.
5. Tidak ada pembelian label/provider baru. Catat jumlah observasi development
   yang diputar ulang, operasi aktual, waktu CPU/wall dan peak RSS host. Label
   sintetis/public reuse, latensi HP/baterai serta real B/C tetap NOT_ASSESSED.

## Keputusan dan stopping

H1–H4 gagal bila kontrol terkait lolos salah, bukti tidak tersimpan atau batas
tidak dihormati. Perbaikan bug diikuti rerun yang relevan; simpan kegagalan awal.
Jangan menambah operator untuk mengejar skor terminal. Kegagalan semantik tersembunyi
di PR #95 harus tetap dilaporkan. Publish draft PR ditumpuk pada branch PR #95;
jalankan exact-SHA CI dan simpan hasil aktual. Tidak merge/deploy/daemon/main/biaya.
Scientific `NOT_ASSESSED`; release `BLOCK_RELEASE`; OAIE `NOT_ESTABLISHED`.
