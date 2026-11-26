# Aktivasi Self-Send ACE — Kirim Tes Terawasi

Tanggal: 2026-11-24 (WIB). Jenis: kirim tes pertama yang terawasi,
sesuai desain `handover/DESAIN_KIRIM_SENDIRI_ACE_20261116.md` —
penanda `ACE_SELF_SEND_ENABLED` hanya bertahan bila kirim tes ini
berhasil.

Yang terjadi:
- Pemilik (tes) menyatakan GitHub dibebaskan untuk ACE dan
  menyediakan kredensial `gh` di rumah eksekusi mesin ini lewat
  alur perangkat GitHub (tindakan operator, sesuai desain;
  nilai kredensial tidak pernah dipegang modul maupun agen).
- Agen pertama ACE (Muse) menjalankan kirim tes ini secara
  terawasi: satu branch `ace-auto/`, satu PR draft, tanpa merge.

Pagar yang tetap berlaku (bawaan modul, tidak diubah):
branch baru saja, PR draft saja, tanpa kode merge, daftar
izinkan hanya `handover/` + `evidence/` + berkas audit,
fail-closed di setiap gerbang, semua kiriman teraudit.
