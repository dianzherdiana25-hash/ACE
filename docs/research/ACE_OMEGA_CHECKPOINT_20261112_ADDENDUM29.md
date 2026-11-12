# ACE Ω — Addendum 29, 2026-11-12: Tahap G — Kedaulatan Multi-Otak: Registri, Gerbang Pemecatan, dan Latihan Pemecatan Otak (DRILL_PASS)

## Mesin (PR #130, bertumpuk di atas #129)

- `brain_registry.py`: catatan otak bernama + log peristiwa
  append-only. Otak lokal aktif; layanan eksternal dicatat jujur
  sebagai `declared-unavailable` sampai ada koneksi nyata yang
  disetujui pemilik — registri tidak berpura-pura terhubung.
- Router menegakkan registri secara fail-closed: panggilan ke otak
  yang dipecat gugur dengan `BRAIN_DISMISSED` sebelum inferensi
  apa pun; bila satu-satunya target yang bisa dipilih telah
  dipecat, router berhenti — tidak ada substitusi diam-diam.
  Pemecatan dan pengangkatan kembali adalah tindakan eksplisit
  yang tercatat. Sweep 238 uji OK.

## Latihan pemecatan otak — hasil langsung

Sesuai desain resmi milestone (otak pemimpin dimatikan dengan
sengaja; pengganti melanjutkan dari piagam + ledger; keberhasilan
diukur dari kontinuitas keputusan dan ingatan):

1. Siklus direktur di **Qwen3-8B** (server teratestasi):
   **accepted**, 5 proposal, 316,5 detik. Dua proposal teratasnya:
   desain instrumen G1 dan mekanisme pertumbuhan katalog — persis
   dua item antrean program saat ini.
2. **Pemecatan** qwen3-8b tercatat di registri; panggilan langsung
   sesudahnya ditolak dengan tepat satu kode: `BRAIN_DISMISSED`.
3. Siklus direktur dilanjutkan oleh **Qwen2.5-Coder-3B** (jalur
   CLI) di atas agenda + memori yang sama: siklus tercatat sebagai
   **rejected** oleh validator (proposal ke-3 tidak menyitir
   based_on — pelanggaran disiplin sitasi, kelas yang sama yang
   pernah menggugurkan percobaan pertama siklus #3 di otak 8B),
   92,7 detik.
4. **Kontinuitas terukur:** agenda memuat 2 siklus berurutan tanpa
   celah; audit memori kognitif `chain_ok: true` (5 peristiwa,
   5 catatan aktif). (Satu bug harness latihan dicatat apa adanya:
   pemeriksaan `memory_audit_clean` di driver membaca kunci yang
   salah — verdict latihan tidak bergantung padanya dan keadaan
   memori dibaca dari field auditnya sendiri.)

**Verdict: DRILL_PASS** — dengan dua fakta yang dibedakan secara
tegas. (a) *Kedaulatan keadaan terbukti:* ACE memecat otak
pemimpinnya, menolaknya secara fail-closed, dan otak lain
melanjutkan ledger yang sama tanpa kehilangan keadaan. (b)
*Paritas penilaian tidak terbukti dan memang tidak dijanjikan
doktrin:* otak pengganti yang lebih kecil gagal melewati pagar
validasi pada kesempatan ini. Doktrin multi-otak menjanjikan organ
yang bisa diganti, bukan organ yang sama kuat — dan sekarang
keduanya terukur, bukan diasumsikan.

Catatan direktur pendamping: pemilik melisensikan skala tahap
yang lebih ambisius di dalam mandat yang sama; kategori reserved
(merge, uang nyata, publikasi) tidak berubah.

Status gerbang tidak berubah oleh addendum ini.
