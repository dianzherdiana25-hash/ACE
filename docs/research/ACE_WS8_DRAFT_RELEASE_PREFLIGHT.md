# Preflight draf dan daftar periksa rilis WS-8

`tools.draft_release_preflight` menyusun envelope lokal dari dua commit pin.
Validator mencocokkan target serta base dengan masukan tepercaya, menghitung
ulang diff dan hash blob, dan memberi digest envelope untuk pembaca manusia.
Pola branch `ace-auto/YYYYMMDD-slug` mengikuti desain pengirim di PR #241.
Branch pengembangan PR ini tetap mengikuti aturan `codex/*`.

Daftar periksa manusia

1. Pastikan target, ref base terbaru, head yang akan dikirim, dan maksud tiap
   path. Ulangi validasi bila base atau head berubah.
2. Periksa isi pada commit tersebut untuk rahasia, data pribadi, bukti
   tersegel, dan izin penggunaan. Allowlist path hanya penyaring awal.
3. Tinjau bukti pengujian, batas klaim, serta hasil verifikasi independen.
4. Catat persetujuan manusia atas digest envelope bila memang disetujui.
   Otorisasi pengiriman dan rilis berada pada gerbang terpisah.

```sh
PYTHONPATH=code:. python3 -m unittest tools.test_draft_release_preflight -q
```

SELESAI — 5 tes lokal membuktikan binding terhadap Git lokal dan penolakan
envelope yang diubah, target keliru, hubungan commit yang salah, serta symlink.

TERSISA — usulan isi ulang berupa uji antarmuka dengan pengirim yang
telah diratifikasi pada PR #241 memakai runner tiruan dan approval fixture.

PENGHAMBAT — izin, konfigurasi pengirim, dan kesegaran ref remote harus
dipastikan pada jalur manusia yang berwenang. Hasil lokal selalu
`send_authorized=false`.
