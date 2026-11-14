# PAKET PENAWARAN — Perbaikan Kerentanan Kode Python + Bukti Tersegel + Retest
- Status: DOKUMEN PENAWARAN saja (13 Nov 2026) — belum didaftarkan/dipublish di platform mana pun. Menunggu gerbang hub/pemilik untuk tindakan akun.
- Dasar kemampuan: PR #145 (services demand test) + Uji Keamanan-01.

## PAGAR KLAIM (mengikat, dari klarifikasi ruang lingkup PR #145, commit 3010cbd)
> "The bundle's discovery/review component — finding not-yet-known vulnerabilities in arbitrary client code — is **not yet demonstrated** by ACE; what is demonstrated is the **fix + sealed before/after evidence + retest on an identified vulnerability** (Uji Keamanan-01)."

Konsekuensi penawaran (tidak boleh dilanggar di listing/proposal mana pun):
- Yang dijual = **perbaikan** atas kerentanan yang **sudah teridentifikasi/dinamai** (oleh klien, hasil scanner klien, atau laporan yang klien serahkan) + bukti before/after tersegel + retest. Kelas yang terdemonstrasi penuh saat ini: **SQL injection** pada kode Python.
- Pemeriksaan terarah HANYA pada kelas yang klien namai, pada modul yang klien serahkan — dirumuskan sebagai pemeriksaan, **tanpa janji penemuan**.
- DILARANG kata/frasa: "pentest", "menemukan semua kerentanan", "jaminan aman", "audit kepatuhan/SOC 2/ISO" (credential-gated, bukan milik kita), janji penemuan kerentanan arbitrer.

---

## VERSI INDONESIA (untuk Fastwork)

**Judul:** Perbaikan Kerentanan Kode Python + Bukti Before/After Tersegel + Retest

**Isi penawaran:**
Punya temuan kerentanan dari scanner atau laporan keamanan, tapi belum diperbaiki? Saya perbaiki kerentanan yang sudah teridentifikasi pada kode Python Anda — dan saya buktikan perbaikannya: Anda menerima bukti before (kerentanan terbukti bisa dieksploitasi pada kode asli) dan after (eksploitasi yang sama gagal setelah perbaikan) yang tersegel hash, lalu retest untuk memastikan perbaikan tidak merusak fungsi lain. Syarat: kode dan akses pengujian hanya dengan izin tertulis pemilik kode.

**Yang Anda terima:** (1) kode yang sudah diperbaiki, (2) laporan temuan→perbaikan per kerentanan, (3) berkas bukti before/after tersegel, (4) hasil retest.

**Yang TIDAK dijanjikan:** penemuan kerentanan baru di luar yang Anda namai, pentest jaringan/aplikasi live, sertifikasi kepatuhan apa pun, jaminan "100% aman".

**Tiga tingkat (jangkar pasar Fastwork terverifikasi PR #145: audit dasar Rp300rb; source-code review Rp1jt; paket dengan retest Rp1,5jt):**
| Paket | Isi | Harga |
|---|---|---|
| Perbaikan Tunggal | 1 kerentanan teridentifikasi (kelas dinamai klien), fix + bukti + retest | Rp350.000 |
| Perbaikan Ganda | s.d. 3 kerentanan dalam kelas yang dinamai + pemeriksaan terarah kelas tsb pada modul yang diserahkan | Rp850.000 |
| Bundel Bukti Lengkap | s.d. 5 kerentanan + laporan bukti tersegel lengkap + 1× retest ulang terjadwal | Rp1.500.000 |

## ENGLISH VERSION (for Upwork / Fiverr)

**Title:** Fix Your Identified Python Vulnerability — With Sealed Before/After Evidence + Retest

**Offer:**
Already know the vulnerability (from your scanner, a report, or a code review) but need it actually fixed — and proven fixed? I repair identified vulnerabilities in Python code and prove it: you receive sealed before-evidence (the vulnerability demonstrably exploitable on the original code) and after-evidence (the same exploit fails on the fixed code), plus a retest confirming nothing else broke. Written permission from the code owner is required; work is performed only on code you submit.

**You receive:** (1) the fixed code, (2) a finding→fix report per vulnerability, (3) the sealed before/after evidence bundle, (4) retest results.

**Explicitly NOT promised:** discovery of new vulnerabilities beyond the ones you name, penetration testing of live systems, any compliance certification (SOC 2 / ISO / PCI), or a "100% secure" guarantee.

**Tiers (anchors: demand-test transaction band $300–$1,500 on Upwork; Fiverr audit-and-fix gigs $35–$400):**
| Platform | Starter | Standard | Complete |
|---|---|---|---|
| Upwork (fixed-price) | $300 — 1 identified vuln, fix + sealed evidence + retest | $750 — up to 3 vulns in named classes + directed check of those classes on submitted modules | $1,500 — up to 5 vulns + full sealed evidence bundle + 1 scheduled re-retest |
| Fiverr (gig) | $80 — 1 identified vuln, fix + evidence summary | $195 — up to 3 vulns + full sealed evidence | $400 — up to 5 vulns + evidence bundle + re-retest |

## Catatan penyusun (bukan bagian dari teks listing)
- Komisi platform: Fastwork **12%** untuk pemula Bronze (TERVERIFIKASI 13 Nov 2026 dari Commission T&C resmi — lihat PELUANG_RESOLUSI_PERINGATAN.md butir 1; contoh 10% di artikel bantuan adalah versi lama), Upwork 0–15% variabel + biaya Connects untuk bidding, Fiverr 20%. Harga di atas harga listing (sebelum komisi).
- Urutan etalase yang disarankan tetap: Fastwork dulu (gerbang terendah), paket yang sama diangkat ke Upwork/Fiverr tanpa produksi ulang.
- Kata "audit" dipakai hub sebagai nama paket internal; di teks publik judul memakai "perbaikan/fix" agar tidak menjanjikan review-discovery yang belum terdemonstrasi.


---

## ADDENDUM — 13 Nov 2026: rel pembayaran langsung QRIS (pemilik)
Pemilik menyerahkan QRIS GoPay Merchant (merchant **KINNEH USAHA MANDIRI GROU**, NMID ID1026571630742; gambar: ~/workspace/ace-omega/handover/QRIS_KINNEH_USAHA_MANDIRI.jpg). Paket ini kini punya DUA rel pembayaran:
- **Via platform (Fastwork/Upwork/Fiverr):** tetap jalur utama untuk klien baru/orang asing — nilai platform adalah penemuan + escrow/kepercayaan, dan komisi (Fastwork 12% dst.) adalah harga dari dua hal itu. Harga listing di dokumen ini tidak berubah.
- **Langsung via QRIS:** untuk klien dari DM/rujukan/pengulangan yang tidak membutuhkan escrow platform — pembayaran QRIS ke merchant pemilik, tanpa potongan komisi marketplace. **Catatan jujur:** QRIS bukan nol-biaya; MDR/feenya berlaku sesuai ketentuan yang berjalan (angkanya tidak diklaim di sini karena belum diverifikasi dari sumber resmi untuk merchant ini). Harga langsung = harga tier yang sama; selisihnya adalah tidak adanya potongan platform, bukan diskon.
- Addendum ini tidak mengubah vonis/angka terverifikasi mana pun di dokumen induk; ia hanya mencatat opsi pembayaran baru pada paket yang relevan (pola yang sama berlaku untuk paket direct lain: fasilitasi taaruf, kurasi playlist, produk digital di luar etalase).

### Catatan lanjutan addendum — MDR QRIS kini TERVERIFIKASI (13 Nov 2026, riset W8 Peta #4)
Kalimat "angkanya tidak diklaim" pada addendum di atas kini terisi dari sumber resmi (halaman QRIS Bank Indonesia + Siaran Pers BI 28/159/DKom + GoPay Merchant; efektif 1 Okt 2026): Usaha Mikro ≤Rp500 rb = **0%**, >Rp500 rb = **0,3%**; merchant reguler ≤Rp100 rb = **0%**, >Rp100 rb = **0,7%**; batas transaksi Rp10 jt; MDR ditanggung merchant dan dilarang dibebankan ke konsumen. Yang masih ⚠️: kategori merchant pemilik (UMI vs UKE) di GoPay Merchant — penentu 0% vs 0,7% pada tiket Rp350–500 rb; perlu cek di aplikasi pemilik dan dicatat di ledger.
