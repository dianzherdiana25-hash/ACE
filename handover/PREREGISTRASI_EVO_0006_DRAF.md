# PREREGISTRASI EVO 0006 — DRAF (Ian, 2026-11-16 malam)
## Uji inheritance memory-store: instans segar di-seed vs dari nol

## §1 Klaim

Instans ACE yang segar (workspace + keadaan proses baru)
yang cognitive_memory-nya di-seed dengan STORE PENUH
program berperilaku terukur lebih baik pada himpunan
probe terkalibrasi daripada instans segar yang mulai
dari store kosong — dibaca lewat jalur recall yang sama
dengan yang diuji EVO 0005 (konteks hasil recall_context
disisipkan ke proposer di ratification_loop).

## §2 Store penuh — definisi persis (diukur sebelum dirancang)

Fakta terukur 16 Nov malam: store live engine
(/workspace/ace-workspace/cognitive_memory) hanya berisi
**2 record** (seed; cycle engine tidak menulis record
cognitive_memory — temuan audit absorpsi 15 Nov masih
berlaku). Store akumulasi EVO 0005 (salinan) berisi 10
record (2 seed yang sama + 8 verdict_sealed). "Store
penuh" untuk misi ini = GABUNGAN keduanya, dideduplikasi
per id record: 2 + 8 = **10 record unik** (8 verdict_sealed
+ 2 seed). Snapshot gabungan dibekukan sebagai berkas
di staging lari dengan sha256 tercatat di catatan lari;
store live TIDAK diubah oleh misi ini (salinan baca-saja).

## §3 Lengan

1. **SEEDED**: workspace segar; cognitive_memory = snapshot
   §2; setiap episode probe dijalankan lewat
   ratification_loop dengan konteks = recall_context
   (query instruksi, kinds semua, limit 10) atas snapshot.
2. **KOSONG**: workspace segar; cognitive_memory kosong;
   jalur identik (recall atas store kosong menghasilkan
   konteks kosong menurut konstruksi).
Kedua lengan: tanpa write-back selama probe
(memory_root=None) agar tidak saling mencemari; konteks
yang disuntikkan per episode DICATAT sebagai field
kelas-satu (syarat diagnosis 0005 §4.1).

## §4 Korpus + kalibrasi pita sensitivitas (syarat diagnosis §4.2)

Korpus kandidat beku: 24 episode (cd-code-001..012,
cd-lang-001..012), sha256
1d09d590fc370cebbdbe55718daf34a79568a1ffa3f32f642903ce029ed3c800
— dibangun menarget pita tengah (jebakan tepi pada code;
kendala bentuk ketat pada language), disjoint dari
korpus 0003/0004/0005.

LAYAR KALIBRASI (sebelum lengan): setiap kandidat
dijalankan 2× pada kondisi KOSONG. Episode masuk
himpunan ukur (probe set) hanya bila vonisnya BELAH
(1 dari 2 ratified). Probe set dibekukan + sha-nya
dicatat di catatan lari sebelum lengan SEEDED berjalan.
Bila probe set < 8 episode, misi berhenti di gerbang
sebagai INSTRUMEN_TIDAK_CUKUP — tidak ada vonis paksa.

## §5 Vonis

- **Gerbang pengantaran** (diagnosis §4.1): bila konteks
  non-kosong terkirim pada < 75% episode lengan SEEDED,
  vonis = **TIDAK_TERANTAR** (recall tidak menjangkau
  isi store untuk tugas-tugas ini) — bukan NOL.
- **TERDUKUNG** iff gerbang lolos DAN rate SEEDED >
  rate KOSONG pada probe set.
- **NOL** iff gerbang lolos DAN rate SEEDED <= rate KOSONG.
- Rincian per-jenis (code/language) dilaporkan apa
  adanya; efek minimum yang bisa ditangkap probe set
  dinyatakan di catatan lari dari ukuran set-nya.

## §6 Ikatan

Rumah ukur sandbox, engine live dijeda selama jendela
(pola 0004/0005), hidup lagi sesudahnya. Store live
tidak diubah. Tidak ada model/venue/front baru. Tidak
ada merge. Lari hanya sesudah paket ini ter-ratifikasi
hub; layar kalibrasi adalah bagian dari lari yang sama.
