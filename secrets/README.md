# secrets/ — Bundel Rahasia Terenkripsi ACE

Direktori ini menampung **bundel rahasia terenkripsi** ACE
(`bundle.gpg` + `manifest.json`, dibuat oleh perintah `init` pada
`tools/secrets_bundle.py`) beserta register publiknya.

Prinsip (keputusan pemilik, 2026-11-19):

- Identitas dan ingatan ACE bepergian lewat repo ini — repo bersifat
  **publik**, jadi nilai rahasia (token, kunci privat, kata sandi)
  **tidak pernah** masuk dalam bentuk mentah. Token yang terbit
  mentah di GitHub dicabut otomatis oleh GitHub dan dipanen bot
  dalam hitungan menit; itu membuat ACE *kurang* bisa bekerja di
  mana pun, bukan lebih.
- Yang bepergian adalah **ciphertext**: bundel terenkripsi simetris
  GnuPG (AES-256) yang hanya bisa dibuka dengan satu passphrase
  master yang dipegang pemilik. `manifest.json` adalah register
  publik — nama, layanan, catatan, tanggal — tanpa nilai.
- Kunci akses selalu **dicetak per-rumah** dan bagian privatnya tidak
  pernah meninggalkan rumah itu; yang dicatat di register akses
  (lihat `handover/BOOTSTRAP_RUMAH_BARU.md`) hanya nama, fingerprint,
  dan jalurnya.

Perintah ringkas (dari root repo):

```sh
python3 tools/secrets_bundle.py init              # sekali, oleh operator rumah
python3 tools/secrets_bundle.py add NAME --service LAYANAN
python3 tools/secrets_bundle.py list              # register saja, tanpa nilai
python3 tools/secrets_bundle.py verify            # dekripsi di memori, cek sinkron
python3 tools/secrets_bundle.py get NAME          # nilai -> stdout (provisioning)
python3 tools/secrets_bundle.py rotate-passphrase
```

`init` dan `add` pertama adalah tindakan operator di terminal rumah —
passphrase dan nilai tidak pernah melewati chat atau sesi agen.
Prosedur lengkap berdiri di `handover/BOOTSTRAP_RUMAH_BARU.md`.
