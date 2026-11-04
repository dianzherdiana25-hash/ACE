# ACE E1.3 — rancangan sebelum penguncian

**Status HOLD.** Kontras, aturan keputusan dan metode analisis di bawah dapat direproduksi. Penguncian konfirmatori memerlukan runner, bank, dan biaya yang lulus pemeriksaan di bagian terakhir. Belum ada hasil konfirmatori.

## Kontras dan pembanding

Bandingkan `C_EXTEND − B_BEAM` pada target dengan motif baru terkait. Beam dipilih sebagai B* pada [selection internal](../../evidence/e13/selection_summary_v1.json), lalu direproduksi sebagai [pekerjaan teknis terpisah](../../evidence/e13/selection_reproduction_v1.json). Pakai solver, interpreter dan kontrak fit dari freeze kandidat `2d9d86c1d7a142f985ea1188532508bca077522c`. Pertahankan delapan kondisi yang sudah dijalankan dan acuan berinformasi `STRUCTURED_ORACLE` dari [desain utama](E13_DESIGN_v0.1.md). Acuan tersebut melaporkan solver dengan kelas grammar diketahui, instance laten dan label probe tersembunyi.

## Estimand, analisis dan kegagalan

Satu arm memuat delapan probe, empat ukuran biasa dan empat ekstrapolasi. Skor primer menggunakan bobot sama untuk kedua ukuran. Laporkan masing-masing ukuran secara terpisah. Hitung selisih C dan beam pada episode dan seed yang sama. Rata-ratakan berturut-turut seed dalam episode, episode dalam blok aturan, blok dalam keluarga, dan kedua keluarga dengan bobot sama. Blok aturan yang benar-benar independen menjadi unit bootstrap. Satukan motif atau generasi aturan yang bergantung pada induk yang sama ketika menentukan blok efektif.

Gunakan bootstrap persentil berstrata S/G 95% dengan 10.000 draw dan seed 131508. Sampel ulang selisih per blok sehingga pasangan kebijakan tetap utuh. Simpan estimasi, interval gabungan, interval per keluarga, denominasi dan rincian cap. Dukungan awal memerlukan estimasi minimal +10 poin persentase, batas bawah interval positif, dan seluruh gerbang integritas/biaya lulus. Batas atas di bawah +10 poin berarti efek minimum tidak didukung. Kasus lain inkonklusif. Kesimpulan per keluarga mempertimbangkan arah dan interval masing-masing.

Setiap kandidat dan pembanding menerima seed uint32 yang sama pada episode/slot yang sama. Gunakan tiga slot per episode. Usulan deterministik adalah empat byte awal SHA-256 dari array JSON kanonis `["ACE-E13-v1", family, opaque_block_id, opaque_episode_id, seed_slot]`, big-endian. Acak urutan arm dengan seed 131510. Kunci implementasi dan daftar arm sebelum eksekusi.

Kegagalan kandidat yang teridentifikasi tetap masuk denominator. AST cadangan valid dinilai, sedangkan arm dengan timeout atau AST invalid bernilai nol sesuai desain. Gangguan infrastruktur/evaluator menahan run dan boleh direkonsiliasi hanya dengan kunci arm idempoten serta digest yang sama. Analisis menolak pasangan hilang, duplikat, jumlah seed/probe yang berubah, atau status yang belum terselesaikan. Bukti harus melaporkan hasil C_NO_EXTEND, C_NO_TRANSFER, dan C_SHAM, termasuk transfer negatif pada strata tak terkait.

## Daya dan biaya

Simulasi memakai 2.000 studi per skenario dan 999 draw bootstrap per studi, seed 131509, NumPy 2.3.5. Efek blok berpasangan disimulasikan dengan distribusi beta pada rentang −1 sampai +1, independen dalam keluarga. Variasi antarblok diuji hingga simpangan baku 0,45. Pilot publik hanya punya dua episode terkait per keluarga dan memakai variasi keluaran dalam motif yang sama. Ukuran efeknya tidak dipakai sebagai ramalan. Daya di bawah ini mengukur peluang melewati aturan keputusan statistik pada skenario yang ditetapkan.

| Blok per keluarga pada rezim terkait | Efek riil +10 poin, SD 0,35–0,45 | Efek riil +15 poin, SD 0,35 | Efek riil +15 poin, SD 0,45 |
| --- | ---: | ---: | ---: |
| 16 | 27,5–40,3% | 70,3% | 49,2% |
| 48 | 49,6–50,1% | 91,9% | 86,5% |

Pada efek riil +10 poin, batas bawah interval saja melewati nol pada 57,7–81,7% simulasi dengan 48 blok. Syarat tambahan bahwa estimasi juga mencapai +10 poin menurunkan peluang keputusan penuh ke sekitar separuh. Pada skenario tidak seimbang S +25/G +5, peluang keputusan gabungan 89,1%, sedangkan peluang batas bawah kedua keluarga positif 11,7%. Skenario simulasi bersifat kondisional dan tidak menetapkan kekuatan bukti pada bank yang belum dibangun. [Bukti simulasi](../../evidence/e13/preconfirm_power_v1.json)

Ukuran rencana adalah **48 blok per keluarga per rezim**, dua episode per blok, tiga seed per episode. Dari grid yang diuji, ini ukuran pertama yang mencapai batas bawah interval Monte Carlo 80% pada tiga alternatif desain +15 poin. Dengan rezim terkait dan tak terkait yang seimbang, totalnya 192 blok, 384 episode, 1.152 unit episode-seed, dan 10.368 arm untuk sembilan kebijakan. Pengulangan probe dan seed tidak menaikkan jumlah blok efektif.

Profil publik menguji 288 arm untuk delapan kebijakan. Tidak ada cap penilaian, empat fit enumeratif mencapai plafon langkah, dan CPU fit + prediksi tertinggi sekitar 107 ms. Proyeksi delapan kebijakan untuk desain penuh sekitar 384 CPU-detik dan 476 detik wall pada beban publik terukur. Batas sembilan kebijakan adalah 10.368 CPU-detik dan 31.104 detik wall untuk arm, ditambah biaya benchmark, oracle dan audit. Cadangan dan kemampuan melanjutkan run perlu dibuktikan sebelum menerima proyeksi itu. [Profil sumber daya](../../evidence/e13/public_resource_profile_v1.json)

## Gerbang menuju lock

- Siapkan bank evaluator konfirmatori dengan 48 blok efektif per keluarga per rezim, demonstrasi yang membedakan kandidat aturan, saksi semantik, dan audit terhadap development dan selection. Kunci digest generator, oracle, bank, manifest, schema, serta versi perangkat analisis. Simpan data dan label di jalur evaluator.
- Siapkan acuan berinformasi yang sesuai kontrak. Ukur biaya oracle/evaluator dan klasifikasikan timeout kandidat versus gangguan infrastruktur. Profil publik delapan kebijakan belum mencakup acuan kesembilan.
- Ledger SQLite evaluator sudah diuji pada worker dan fixture publik. Ia mengikat digest kandidat, bank, oracle, protokol dan daftar arm, serta melanjutkan arm yang belum terminal. Integrasi dengan verifikasi lock bank privat, klasifikasi kegagalan dari adapter dan pembatas biaya total tetap terbuka. Tahan run bila kuota, jumlah blok efektif, atau integritas split tidak memenuhi rancangan.
