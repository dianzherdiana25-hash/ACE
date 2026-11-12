# ACE Ω — Addendum 3, 2026-11-12: OMEGA-04 durable task workflow (audit + uji)

Fase 1 berlanjut. Paket ini tidak menambah komponen baru: fondasi workflow
durable ACE sudah ada (`OperationalStore` + Mission Bus di `main`,
`LocalRepoWorkflow` di #104). Yang dikerjakan adalah verifikasi independen
di VM operator.

## Yang terverifikasi

1. **Mission Bus + admission (kode `main`)**: suite `ace_mission.test_mission_bus`
   dan `ace_mission.test_admission` — **31 test lulus** di VM ini.
2. **Durabilitas lintas proses (`OperationalStore`, kode `main`)**: probe
   tiga proses OS terpisah — proses A membuat task + checkpoint
   (`stage: designed`) + event; proses B membuka ulang workspace yang sama
   dan menemukan task, checkpoint, dan jejak event utuh, lalu memajukan
   checkpoint (`stage: implemented`); proses C memverifikasi keadaan akhir.
   **Verdict: PASS.** Evidence: `evidence/omega04_crash_resume.json`.
3. **Semantik checkpoint workflow** (dari suite #104 yang berjalan di VM ini):
   task yang terinterupsi di tengah jalan menghasilkan `HOLD` — bukan
   replay buta; replay hasil terverifikasi ditolak bila pohon kandidat atau
   postimage berubah (tamper control).

## Yang tidak diklaim

- Tidak ada durabilitas multi-host atau daemon yang hidup melewati restart
  runtime VM ini (proses terbukti mati saat runtime restart; checkpoint di
  disk yang membuat pekerjaan dapat dilanjutkan, bukan prosesnya).
- Mesin lease/epoch pada store tidak diuji beban/konkurensi pada sesi ini.
- OMEGA-04 belum mempunyai gerbang sendiri di Master Prompt; status paket
  ini: fondasi terverifikasi untuk lingkup lokal satu host.

## Aksi berikutnya

- OMEGA-06 (evaluasi independen) dan OMEGA-08 (populasi & lineage) adalah
  paket Fase 1 berikutnya yang prasyaratnya terpenuhi sebagian; keduanya
  pekerjaan multi-sesi.
- Fase 2 (loop Research Director otomatis) tetap menunggu Fase 1, sesuai
  keputusan pemilik.
