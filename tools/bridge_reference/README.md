# bridge_reference — sumber acuan rantai kurir EVO 0009 (BUKAN kode produksi)

Tiga berkas ini adalah implementasi yang SEDANG BERJALAN untuk rantai
kurir engine sandbox → organ API, disalin apa adanya dari rumah kerja
VM Ian (~/workspace/evo0009-build) + sisi sandbox pada 2026-11-20:

- `bridge.py` — bridge di VM: endpoint /health /chat /embed /budget di
  127.0.0.1:8931, governor budget per peran per hari, log panggilan.
- `relay_pump.py` — pump di VM: memompa berkas spool req/resp antara
  sandbox dan bridge lewat scp/sshdrive.
- `bridge_relay.py` — relay di sandbox: menerima panggilan engine di
  127.0.0.1:18931, menulis spool, menunggu respons sampai deadline.

Status: REFERENSI untuk pekerjaan EVO 0016 (bridge menjadi perkakas
repo yang terawat: tools/brain_bridge.py dkk.). Jangan mengimpor dari
direktori ini; jangan mengubah perilaku protokolnya di sini.
