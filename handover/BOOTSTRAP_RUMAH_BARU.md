# Bootstrap Rumah Baru ACE

*Runbook pendirian rumah eksekusi ACE dari nol — supaya ACE bisa
bekerja di rumah mana pun tanpa bergantung pada satu sesi atau satu
agen. Ditulis 2026-11-19 atas keputusan pemilik: "biar di manapun
bisa ngerjain tanpa perlu kamu". Contoh nyata yang dirujuk berulang
di dokumen ini adalah pendirian jalur push VM Ian pada hari yang
sama (kunci SSH "Ian-SSH").*

## 1. Prinsip

1. **Identitas dan ingatan bepergian lewat repo.** Konstitusi,
   catatan, kode, memori program, dan dokumen serah-terima ada di
   repo ini. Rumah baru yang me-clone repo mewarisi semuanya.
2. **Repo ini publik — nilai rahasia tidak pernah masuk mentah.**
   Token/kunci/kata sandi dalam bentuk mentah akan dicabut otomatis
   oleh platform (GitHub menonaktifkan PAT yang terdeteksi bocor)
   dan dipanen bot. Nilai rahasia hanya tinggal di dua tempat:
   Secure Vault pemilik, atau bundel terenkripsi di `secrets/`
   (ciphertext GnuPG AES-256, dibuka dengan satu passphrase master
   yang dipegang pemilik).
3. **Kunci dicetak per-rumah; bagian privat tidak pernah
   meninggalkan rumah itu.** Yang dicatat untuk semua rumah adalah
   registrasi publiknya: nama kunci, fingerprint, jalur, tanggal
   (lihat §5).
4. **Satu-satunya tindakan yang secara fisik tangan pemilik:**
   menambahkan kunci publik rumah baru ke akun GitHub (±1 menit)
   dan, sekali saja, membuat passphrase master bundel. Selebihnya
   dikerjakan rumah itu sendiri atau agen yang bertugas di sana.

## 2. Syarat rumah

- `git`, `python3` (≥3.10), `gpg` 2.x, klien OpenSSH.
- Akses internet keluar: clone/push GitHub (HTTPS untuk baca;
  SSH lewat `ssh.github.com:443` untuk tulis — port 443 dipilih
  karena banyak jaringan menutup port 22).
- Ruang disk cukup untuk repo + artefak kerja rumah itu.

## 3. Langkah pendirian

```sh
# 1) Ambil repo (publik — baca tidak butuh kredensial)
git clone https://github.com/dianzherdiana25-hash/ACE.git
cd ACE
git log --oneline -1            # catat head main sebagai basis rumah

# 2) Verifikasi bawaan repo utuh
python3 tools/verify_sources.py # harus PASS

# 3) Cetak kunci SSH rumah INI (privat tidak keluar dari rumah ini)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "ace-home-<nama-rumah>"
ssh-keygen -lf ~/.ssh/id_ed25519.pub   # catat fingerprint SHA256-nya

# 4) PEMILIK menambahkan kunci publik ke GitHub:
#    Settings -> SSH and GPG keys -> New SSH key (Read/write).
#    Contoh nyata: "Ian-SSH", ditambahkan 2026-11-19.

# 5) Pasang remote tulis dan uji
git remote add sshpush ssh://git@ssh.github.com:443/dianzherdiana25-hash/ACE.git
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes" \
  ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes -T -p 443 git@ssh.github.com
#    -> "Hi dianzherdiana25-hash! You've successfully authenticated..."
GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes" \
  git ls-remote sshpush refs/heads/main   # harus == head pada langkah 1

# 6) Daftarkan rumah ini di register akses (dokumen ini, §5) lewat
#    satu PR kecil: nama rumah, nama kunci, fingerprint, jalur, tanggal.
```

Catatan propagasi: autentikasi bisa gagal pada percobaan pertama
tepat setelah kunci ditambahkan (kasus 2026-11-19) — tunggu ±1 menit
dan coba lagi sebelum menyimpulkan kunci salah; bandingkan
fingerprint lokal dengan yang tampil di GitHub.

## 4. Bundel rahasia (provisioning kredensial layanan)

Sekali saja, oleh operator di terminal sebuah rumah (passphrase
tidak pernah melewati chat):

```sh
python3 tools/secrets_bundle.py init
python3 tools/secrets_bundle.py add groq-api --service groq
# nilai dibaca lewat prompt tanpa echo; ulangi untuk tiap kredensial
```

Lalu commit `secrets/bundle.gpg` + `secrets/manifest.json` lewat PR
seperti perubahan lain.

*Status nyata 2026-11-19: atas perintah pemilik ("kamu aja"), `init`
pertama dijalankan Ian di VM Ian. Passphrase master dibuat oleh
mesin (32 byte acak) dan disimpan HANYA sebagai berkas lokal
`~/.ace-secrets/bundle-passphrase` (izin 600) di VM Ian — tidak
pernah tampil di chat, repo, atau catatan mana pun. Bundel lahir
dengan 0 entri. Pemilik dapat mengambil alih passphrase kapan pun
dengan `rotate-passphrase` di terminal rumah mana pun (passphrase
lama dibaca Ian dari berkas itu tanpa menampilkannya), atau meminta
Ian menjalankan `verify`/`get` secara transient dari berkas yang
sama. Pengisian entri terjadi saat sebuah nilai secara sah berada
di tangan operator; nilai yang tersimpan di Secure Vault tidak bisa
diekstrak oleh siapa pun — itu memang desain brankasnya.*

Di rumah baru mana pun setelah itu:

```sh
python3 tools/secrets_bundle.py verify     # minta passphrase master
python3 tools/secrets_bundle.py get groq-api   # nilai -> stdout,
# pasang langsung ke vault/konektor lokal rumah itu lewat pipa;
# jangan pernah menulis nilai ke berkas biasa atau menampilkannya
# di keluaran yang tersimpan.
```

Aturan bundel: passphrase salah atau berkas diubah → dekripsi gagal
tertutup (integritas GPG), tidak ada keluaran sebagian. Rotasi
passphrase: `rotate-passphrase` (interaktif). Rotasi nilai: `add
--force`. Nilai yang pernah tampil di chat/log publik dianggap
**bocor** — rotasi di layanannya, bukan hanya di bundel (preseden:
PAT GitHub 2026-11-16 dan kunci Groq 2026-11-18, keduanya dicabut
pemilik di hari yang sama).

## 5. Register akses (publik — tanpa nilai)

| Rumah / jalur | Nama | Fingerprint / identitas | Jalur | Sejak | Hak |
|---|---|---|---|---|---|
| VM Ian (eksekusi utama) | `Ian-SSH` | `SHA256:zxYrybwUM6iOslwPgzT6IfvIUx7JFahPGGGsOIZqJM8` | `ssh://git@ssh.github.com:443`, remote `sshpush` | 2026-11-19 | GitHub Read/write |
| Sandbox ACE (Manus) | kunci operator sandbox | dikelola operator (kancuto) | SSH `sshremote:443` via Tailscale (`ace-sandbox.taild2ddcb.ts.net`) | 2026-11-15 | shell sandbox |
| Secure Vault (konektor) | `custom.groq`, `custom.gemini`, `custom.gemini2`, `custom.gemini3`, `custom.cloudflare`, dll. | nilai di vault, tidak dicatat di sini | API per konektor | 2026-11-18 | per layanan |

Baris baru ditambahkan saat rumah/jalur baru berdiri; baris dicabut
dari tabel saat aksesnya dicabut di sumbernya.

## 6. Menyalakan kembali ACE di rumah baru

1. Baca berurutan: dokumen ini → `docs/HANDOVER_INDEX.md` →
   serah-terima terakhir di `handover/`.
2. Jalur kirim-sendiri ACE (`code/ace_operational/self_send.py`,
   PR #241) berstatus **dormant** sampai dua tindakan operator di
   rumah itu: provisioning `gh auth` dan pemasangan berkas penanda
   pengaktif setelah satu test send terawasi. Merge kode ≠ aktivasi.
3. Mesin belajar (EVO 0009) berjalan dari clone-nya sendiri di
   sandbox (`/workspace/ace9clone`) dengan bridge store-and-forward;
   rumah baru yang mengambil alih harus menyalakan bridge dan
   memeriksa rantai hash store sebelum siklus dilanjutkan.
4. Pekerjaan berjalan (driver, run) tidak berpindah otomatis antar
   rumah: rumah pengambil-alih memeriksa status terakhir dari
   catatan repo, lalu menyalakan ulang dari checkpoint — preseden:
   driver EVO 0007 mati oleh penggantian VM pada 2026-11-19 dan
   dinyalakan ulang dari baris tersegel terakhir tanpa kehilangan.

## 7. Insiden dan pencabutan

- **Kunci rumah hilang/terekspos:** cabut di GitHub (Settings → SSH
  and GPG keys → Delete), cetak kunci baru di rumah itu, perbarui
  §5. Tidak ada kunci privat yang perlu "diselamatkan" dari rumah
  lain — memang tidak ada salinannya di mana pun.
- **Passphrase master bundel hilang:** bundel tidak bisa dibuka
  siapa pun (termasuk pemilik) — kredensial di dalamnya diterbitkan
  ulang satu per satu di layanannya dan bundel dibuat baru. Karena
  itu passphrase disimpan pemilik di vault, dan nilai penting tetap
  punya rumah kedua di Secure Vault.
- **Nilai tampil di tempat publik:** anggap bocor, rotasi di
  layanan, perbarui bundel/vault, catat sebagai insiden.

## 8. Larangan ringkas

- Tidak ada nilai rahasia di repo, chat, log, nama berkas, atau
  pesan commit — dalam bentuk apa pun, termasuk terpotong atau
  ter-encode.
- Tidak ada kunci privat yang berpindah antar-rumah. Yang berpindah:
  repo (publik), bundel (ciphertext), dan registrasi (publik).
- Tidak ada aktivasi kemampuan baru (penanda self-send, `gh auth`,
  konektor berbayar) sebagai efek samping bootstrap — semuanya
  tindakan bernama yang tercatat.
