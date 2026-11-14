# Workflow Konsistensi Karakter — Serial 1
## *Setelah Diusir, Aku Pulang Sebagai Pemiliknya* (teaser ilustrasi sinematik)

ACE Ω capability item 8, 2026-11-13. Folder ini adalah jangkar
konsistensi tokoh untuk semua kartu teaser berikutnya. TIDAK ADA
yang dipublikasikan dari folder ini; berkas saja.

## Berkas jangkar

| Berkas | Isi |
|---|---|
| `referensi_karakter_utama.png` | Lembar referensi Kirana: satu figur, full-body, menghadap depan, latar abu hangat netral, cahaya rata. **Sekali dibuat, tidak dibuat ulang.** |
| `kartu_konsistensi_a.png` | Uji A — Bab 1, adegan tuduhan: Kirana memegang kotak beludru merah kosong di ruang tamu, Laras (kebaya hijau botol) duduk terpisah. |
| `kartu_konsistensi_b.png` | Uji B — Bab 1, adegan teras kos: Kirana membuka buku catatan bersampul batik, tas kain di kaki, segelas teh mengepul. |

## Sumber kebenaran tokoh

Biblia (`MENULIS_BIBLIA_OPSI1.md`) menetapkan: **Kirana Ayu
Lestari, 29 tahun**, mantan staf administrasi, pengelola dapur +
pembukuan Dapur Wijaya; senjata/prop wajibnya **buku catatan
bersampul batik** dan **tas kain besar**. Biblia tidak merinci
wajah/rambut/busana — rincian visual itu dikodifikasi di sini dari
Kirana *de facto* yang sudah hidup di bank teaser (kartu Bab 2 dan
raw Bab 8 sudah memakai perempuan yang sama: sanggul rendah
longgar, blus batik merah marun) lalu **dibekukan** di lembar
referensi. Sejak dokumen ini ada, lembar referensilah sumber
kebenaran visualnya — bukan ingatan, bukan prompt lama.

## Blok deskriptor karakter TERKUNCI (salin verbatim ke setiap prompt)

```
KIRANA (character lock): a 29-year-old Indonesian Javanese woman,
warm medium-brown skin, oval face with soft cheekbones, straight
nose, dark brown almond eyes, natural brows, no heavy makeup;
black hair worn in a loose low bun with a few stray strands
framing her face; slender medium build; wearing her signature
deep maroon batik-patterned blouse with three-quarter sleeves
and a dark indigo batik sarong skirt. Calm, restrained expression
with quiet resolve; tired eyes that do not cry.
```

Jangan parafrase, jangan "diperbaiki", jangan diterjemahkan ulang
per kartu. Perubahan blok ini = perubahan karakter = wajib lewat
revisi dokumen ini + lembar referensi baru.

## Blok gaya TERKUNCI (salin verbatim ke setiap prompt)

```
STYLE LOCK: painterly cinematic digital illustration, rich
visible brush texture like a modern oil painting; warm amber
lantern/bulb light against deep teal-blue shadows, chiaroscuro;
Javanese home or small-town Indonesian setting details; portrait
composition; emotional Indonesian family-drama mood; no text,
no watermark.
```

Ini gaya bank teaser yang sudah berjalan (konsisten di kartu
Bab 2–12): lukisan digital sinematik bertekstur kuas, cahaya
kuning lampu anyaman vs bayangan teal-biru tua.

## Cara lembar referensi mengjangkar kartu baru

Mekanisme kunci yang dipakai (dan yang tersedia di pipeline media
saat ini — **tidak ada parameter seed numerik**, jadi kuncinya
bukan seed melainkan tiga lapis ini):

1. **Gambar referensi sebagai input identitas.** Setiap panggilan
   `media.generate_image` untuk kartu ber-Kirana WAJIB melampirkan
   `referensi_karakter_utama.png` sebagai entri gambar pertama,
   diikuti label identitas, baru teks adegan.
2. **Blok deskriptor verbatim** (di atas) disisipkan utuh di teks
   adegan — termasuk kalimat "keeping her exact same face, hair,
   and signature outfit".
3. **Blok gaya verbatim** menutup prompt.

Aturan turunan:
- Lembar referensi tidak pernah di-regenerasi untuk "memperbaiki"
  hasil kartu; kartu yang meleset yang di-regenerasi.
- Tokoh lain (Arman, Laras, Dita, Rini, Salma, Bima) belum punya
  lembar referensi; bila sebuah bab mulai memakai satu tokoh
  berulang, buat lembar referensinya dengan pola yang sama dulu,
  tambahkan blok deskriptornya ke dokumen ini.
- Busana khas Kirana (marun + indigo) berlaku untuk adegan rumah/
  dapur Bab 1–8. Adegan yang memang menuntut busana lain (mis.
  Bab 12, pemilik ruko) boleh mengganti busana — tetapi wajah,
  rambut, dan kulit tidak pernah ikut berubah; catat pengecualian
  busananya di PR/kartu terkait.

## Hasil uji konsistensi (2026-11-13, dinilai dari keluaran nyata)

| Aspek | Referensi | Kartu A (ruang tamu) | Kartu B (teras kos) |
|---|---|---|---|
| Wajah | Oval, alis natural, hidung lurus, bintik halus di pipi/hidung | **Sama** — wajah yang sama langsung dikenali, termasuk bintik halusnya | **Sama** — identitas tetap terbaca pada sudut 3/4 menunduk |
| Rambut | Sanggul rendah longgar, helai lepas membingkai wajah | Sama; sanggul sedikit lebih longgar/berantakan (masih dalam keluarga gaya yang sama) | Sedikit lebih ketat/tinggi, ada ekor kecil di belakang — **drift terkecil yang tercatat, masih lolos** |
| Busana | Blus batik marun (motif emas + pita motif di ujung bawah) + sarung batik indigo | Sama, motif dan potongan konsisten | Sama; pita motif ujung blus tak terlihat karena posisi duduk (bukan drift) |
| Kulit | Sawo matang hangat | Terlihat sedikit lebih terang — efek cahaya lampu kuning, bukan perubahan identitas | Sama dengan referensi |
| Usia terbaca | ±29 | ±29 | ±29 |
| Prop wajib | — | Kotak beludru merah kosong ✓ (isi memang kosong di cerita) | Buku sampul batik ✓, tas kain ✓, teh mengepul ✓ |

**Vonis uji: LULUS.** Dua adegan yang sangat berbeda (ruang tamu
ramai di bawah lampu anyaman vs teras kos malam hari) menampilkan
perempuan yang sama tanpa regenerasi lembar referensi. Drift nyata
hanya dua: keketatan sanggul (B) dan terang kulit karena cahaya
(A) — keduanya di dalam toleransi aturan lulus di bawah.

## Aturan LULUS/GAGAL kartu berikutnya

Sebuah kartu **LULUS** bila semua ini benar saat dibandingkan
berdampingan dengan `referensi_karakter_utama.png`:

1. Wajahnya dikenali sebagai orang yang sama (bentuk wajah, alis,
   hidung, bibir) pada sudut adegan apa pun.
2. Rambut hitam, sanggul rendah (longgar boleh, ketat masih boleh;
   ganti model/warna = gagal).
3. Busana khas marun + indigo hadir bila adegan tidak menuntut
   busana lain secara eksplisit.
4. Usia terbaca 27–32 tahun.
5. Warna kulit sawo matang hangat; pergeseran hanya boleh sejauh
   yang bisa dijelaskan cahaya adegan.

**GAGAL** bila satu saja dilanggar → regenerasi dengan prompt yang
sama (maks. 2 kali). Masih gagal → berhenti, catat di folder ini,
dan jangan paksa dengan mengubah blok deskriptor tanpa merevisi
dokumen ini. Kartu gagal tidak masuk bank teaser.

## Catatan kejujuran

- Pipeline media yang dipakai tidak menyediakan seed numerik;
  klaim "seed terkunci" tidak dibuat. Kunci konsistensi di sini =
  gambar referensi + dua blok verbatim + aturan lulus/gagal.
- Penilaian drift di atas adalah penilaian visual penulis dokumen
  terhadap tiga keluaran nyata di folder ini, bukan pengukuran
  otomatis.
