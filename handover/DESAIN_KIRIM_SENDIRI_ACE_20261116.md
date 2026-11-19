# DESAIN — KIRIM-SENDIRI ACE (draf untuk tinjauan hub)

Prinsip pemilik (2026-11-16 01:35): "ACE sendiri harus mampu mengirim
ke GitHub." Dokumen ini DESAIN — pembangunan menunggu tinjauan hub.

## 1. Inventaris — apa yang sudah ada hari ini

- **`AutonomousPRManager`** (`code/ace_code_agent/pr_manager.py`, 313
  baris): rantai lengkap sudah ada — siapkan metadata → buat branch +
  commit → `git push -u origin <branch> --force` → buat PR via **gh CLI**
  → verifikasi. Komentar kodenya sendiri mencontohkan URL
  `.../pull/90` — **PR #90 memang lahir dari manajer ini**, satu-satunya
  PR buatan engine sampai hari ini.
- Pemanggil: `ace_code_agent/controller.py` (siklus patch otonom);
  tes-tes mem-mock jalur publish (`test_audit_regressions`) dan
  memeriksa "safety namespace" (`test_operational_proof`).
- `LocalRepoWorkflow` (`ace_operational`): kerja repo lokal murni —
  menolak branch main/master, menghasilkan patch + catatan; TANPA push.
  Ini pola tata kelola yang benar untuk ditiru: bernama, bercabang,
  tercatat.

## 2. Kesenjangan — apa yang hilang

1. **Kredensial ambient, tak terverifikasi.** `git push` + `gh` bergantung
   pada auth yang kebetulan ada di rumah eksekusi. Di sandbox, keadaan
   auth gh/git untuk origin BELUM terverifikasi (pintu jatuh saat
   inventaris ini ditulis). Mesin tidak bisa mencetak kredensialnya
   sendiri — penyediaan auth adalah tindakan operator (kancuto/pemilik),
   sekali, lewat jalur aman sandbox; nilainya tak pernah tertulis di
   kode, catatan, atau chat.
2. **Push --force.** Manajer memaksa push. Untuk kirim-sendiri yang
   tertata, force tak pernah perlu: branch selalu BARU dan bernama.
3. **PR tidak draft.** `gh pr create` tanpa `--draft` — bertabrakan
   dengan disiplin rumah (semua kiriman mesin = draft; merge bukan
   wewenang mesin).
4. **Tanpa allowlist isi.** Belum ada batas jalur berkas yang boleh
   dikirim mesin (catatan, bukti, write-back ingatan) vs yang tidak
   (kode inti, kredensial, ledger privat).
5. **Pemicu belum terikat ke write-back ingatan.** Jalur tulis ingatan
   (PR #235) menulis lokal; tak ada langkah "flush ke GitHub" yang
   menjadikannya catatan persisten sesuai prinsip GitHub = ingatan
   persisten ACE.
6. **Tak ada catatan audit per kiriman** yang terikat ke registri misi
   (siapa memicu, branch apa, digest isi apa, PR nomor berapa).

## 3. Rancangan — `ace_self_send` (pembungkus tertata di atas manajer)

Satu modul tipis BARU (`code/ace_operational/self_send.py`) yang MEMAKAI
AutonomousPRManager untuk mekanik git/gh, dan menambahkan tata kelola:

- **Namespace branch keras:** hanya `ace-auto/<tanggal>-<slug>`; menolak
  nama lain, menolak target selain repo ACE, menolak push ke branch yang
  sudah ada (non-force; branch ada = kiriman duplikat, berhenti).
- **Draft saja:** `gh pr create --draft`; modul tidak memiliki kode
  merge sama sekali (bukan wewenang mesin — batas pemilik).
- **Allowlist jalur:** hanya `handover/`, `evidence/`, dan berkas
  write-back ingatan yang dihasilkan `memory_writeback` (daftar pola
  eksplisit di konfigurasi modul); berkas di luar allowlist = kiriman
  ditolak sebelum commit. Ledger privat + berkas rahasia masuk denylist
  eksplisit.
- **Kredensial:** dibaca gh/git dari auth store rumah eksekusi (sandbox)
  — modul tidak menerima, menyimpan, atau mencatat nilai kredensial;
  prasyarat `gh auth status` sehat diperiksa sebagai gerbang pra-kirim
  (gagal = kiriman dibatalkan dengan catatan, bukan dicoba-coba).
- **Pemicu:** (a) langkah eksplisit di akhir siklus engine yang sudah
  ada (controller), dan (b) CLI mandiri `python -m
  ace_operational.self_send flush` untuk flush write-back ingatan —
  keduanya hanya jalan bila berkas penanda `ACE_SELF_SEND_ENABLED` ada
  di rumah eksekusi (saklar fisik operator; absen = nonaktif total).
- **Audit:** setiap kiriman menulis satu baris JSONL lokal
  (waktu, pemicu, branch, digest pohon kiriman, daftar berkas, nomor PR)
  dan baris yang sama ikut ter-commit — rantai bukti kiriman hidup di
  repo itu sendiri.
- **Fail-closed:** kegagalan di langkah mana pun menghentikan kiriman,
  mencatat sebabnya, dan tidak meninggalkan branch setengah jadi di
  remote (push adalah langkah terakhir sebelum PR; kegagalan PR sesudah
  push dicatat dengan nomor branch untuk dibersihkan operator).

## 4. Yang TIDAK berubah

- Merge ke main: bukan wewenang mesin, titik.
- Manajer lama tidak ditulis ulang; pembungkus membatasi perilakunya
  (force dinonaktifkan lewat jalur pembungkus: branch baru selalu).
- Jalur Ian (connector push-files) tetap untuk pekerjaan sesi Muse;
  kirim-sendiri adalah jalur MESIN di rumah sandbox.

## 5. Pertanyaan terbuka untuk hub/operator

1. Penyediaan kredensial: gh auth di sandbox oleh operator — kapan dan
   akun mana (akun GitHub yang sama dianzherdiana25-hash?).
2. Saklar penanda: cukup berkas penanda, atau mau gerbang kedua
   (mis. jendela jam)?
3. Frekuensi flush ingatan: per siklus engine, atau berkala (mis. tiap
   N peristiwa terverifikasi)?

## 6. Ratifikasi hub (2026-11-16) — TER-RATIFIKASI sebagai dasar bangun

- Q2: berkas penanda saja cukup untuk v1; tanpa gerbang jendela jam.
  Nilai lagi sesudah kiriman pertama.
- Q3: flush v1 HANYA pada batch peristiwa kelas ratifikasi
  (verdict_sealed / mission_ratified / skill_verified dari write-set
  PR #235) di akhir siklus kerja yang menghasilkannya, plus CLI manual.
  Bukan per siklus, bukan per-N.
- Q1: penyediaan gh auth di sandbox = tindakan operator (akun
  dianzherdiana25-hash); pembangunan tidak menunggu itu — kiriman live
  pertama yang menunggu.
- Syarat hub: kiriman live pertama adalah KIRIMAN UJI terawasi (satu
  berkas catatan tak berbahaya), ditinjau hub sebelum pemicu diikat ke
  controller; berkas penanda tetap ABSEN sampai uji itu lulus.
- Urutan: modul + tes di sisi VM dulu; loop 0003 tetap prioritas.

## 7. Catatan bangun (Ian, 2026-11-16)

Modul `code/ace_operational/self_send.py` + `test_self_send.py`
(16 tes, hijau di VM pada basis f6d75462) dibangun sesuai §6.
Satu koreksi inventaris terhadap §1/§3 dokumen ini: di main saat
ini, langkah commit AutonomousPRManager TERKUNCI gerbang evaluasi
(mengembalikan "BLOCKED: candidate-bound independent evaluation
unavailable"), push-nya memakai --force, dan pembuatan PR-nya
bukan draft — jadi pembungkus tidak memanggil pipeline manajer,
melainkan menerapkan mekanik tertata langsung (namespace keras,
non-force, draft-only, allowlist+denylist, gerbang auth, audit
JSONL lokal + ter-commit), mengikuti pola verifikasi otoritatif
manajer. Berkas penanda tetap ABSEN; kiriman live pertama tetap
kiriman uji terawasi yang menunggu penyediaan gh auth operator
di sandbox.

## 8. Perkerasan pasca-telaah (Ian, 2026-11-16)

Telaah statik eksternal atas PR #241 menilai amplop v1 belum
aman sebagai pembatas. Lima titiknya diperbaiki berurutan;
non-force + draft-only dipertahankan; tes kini 29 (hijau):

1. **Kunci repo + basis aktual:** send() memverifikasi URL
   origin terkonfigurasi == dianzherdiana25-hash/ACE sebelum
   efek apa pun; branch dibuat DARI ref lokal `main`
   terverifikasi (bukan HEAD aktif); index/worktree kotor
   menolak send; commit dibatasi pathspec allowlist — di-stage
   eksplisit lalu himpunan staged diverifikasi nama-per-nama.
2. **Symlink tertutup:** setiap tujuan tulis (payload + audit)
   wajib ter-resolve di dalam root repo; jalur yang keluar
   lewat symlink ditolak sebelum penulisan.
3. **Marker + audit lengkap:** marker dicek sebelum staging
   apa pun (flush tanpa marker tidak mengekspor apa pun);
   audit lokal mencatat juga flush kosong dan
   exception/timeout; audit ter-commit kini dua fase — baris
   `prepared` di commit isi, baris FINAL (outcome + nomor PR)
   di commit susulan pada branch yang sama, jadi catatan repo
   tidak pernah berhenti di status pending.
4. **Batas batch:** ekspor mengecualikan id yang sudah ter-ack
   persisten (ack hanya bila nomor PR ada); flush kedua di
   hari yang sama mengambil slug bersufiks (-2, -3, …) anti
   benturan.
5. **Tes sungguhan:** kelas TestRealGit menjalankan git nyata
   di repo sementara (remote bare lokal via insteadOf; hanya
   gh yang di-stub): end-to-end + basis main dari HEAD
   non-main, origin salah, worktree kotor, symlink, flush
   tanpa marker, dedup + slug — 7 tes, semuanya hijau bersama
   22 tes gerbang/fake yang disesuaikan.

Penanda tetap ABSEN; kiriman uji terawasi menunggu verifikasi
ulang telaah + penyediaan gh auth operator.

## 9. Putaran 3 — telaah ulang atas head 519be922 (Ian, 2026-11-16)

Telaah ulang menilai perbaikan putaran 2 nyata tetapi amplop
belum lulus: empat bukti regresi dari probe Git sungguhan.
Keempatnya menjadi tes regresi DULU (terbukti gagal pada modul
lama: 9 tes merah), baru diperbaiki. Tes kini 37, hijau.

1. **Target push dipatok penuh:** bukan hanya
   remote.origin.url — seluruh URL push efektif (pushurl bila
   ada, dengan rewrite url.*.insteadOf/pushInsteadOf diterapkan
   sesuai semantik git) wajib mengidentifikasi
   dianzherdiana25-hash/ACE, dan semua panggilan gh membawa
   `--repo` eksplisit (GH_REPO tak bisa mengalihkan).
2. **Basis = origin/main hasil fetch:** branch dibuat dari
   commit basis ter-pin itu (sha-nya tercatat di baris audit),
   tidak pernah dari main lokal — commit sintetis lokal
   berberkas luar-allowlist tidak lagi bisa ikut terkirim.
   Sebelum push, SELURUH diff keluar (basis..branch)
   divalidasi terhadap allowlist dan merge-base wajib persis
   basis ter-pin.
3. **Symlink ditolak di semua komponen:** payload + audit,
   sebelum DAN sesudah checkout (pohon basis hasil fetch),
   sebelum penulisan apa pun; penjaga yang sama di dalam
   fungsi tulis. Symlink di dalam repo yang dulu menimpa
   targetnya kini menolak send tanpa menyentuh berkas.
4. **Flush dalam amplop teraudit yang sama:** ekspor batch
   (dan muat/simpan ack) berada di dalam try yang sama dengan
   send — store rusak = baris audit error, bukan exception
   lolos.
Plus: kegagalan commit/push audit final menghasilkan
sent=False dengan status eksplisit `audit_finalize_failed`
(nomor PR tetap dilaporkan); penulisan ack atomik
(tmp + rename), ack rusak = refusal AckStoreCorrupt (tidak
dibaca sebagai {}), dan ack hanya sesudah send terverifikasi
penuh.

Yang dipertahankan utuh: non-force, draft-only, marker
mendahului staging, dedup + sufiks slug. Penanda tetap
ABSEN; gh auth tetap parkir menunggu verifikasi putaran ini.

## 10. Putaran 4 — vonis akhir atas head d792a666 (Ian, 2026-11-16)

Vonis akhir: BELUM LULUS — dua bypass target yang sudah
terbukti DITAMBAH dua bukti Git nyata baru dan satu perluasan
target. Semua menjadi tes regresi dulu (mekanisme real-git
merah pada modul putaran 3), baru diperbaiki. Tes kini 42.

Koreksi harness lebih dulu: pelari real-git putaran 3
menulis-ulang kata kerja fetch itu sendiri (seam refspec
paksa) — seam itulah yang menyembunyikan peracunan basis.
Harness putaran 4 hanya men-stub PIPA transport
(GIT_SSH_COMMAND ke bare lokal; origin mempertahankan
identitas ACE aslinya dan get-url berkata jujur) dan gh.
Tidak ada mekanisme yang diuji yang di-stub.

1. **Berhenti emulasi semantik Git.** effective_push_urls()
   dan seluruh mesin rewrite-nya DIHAPUS. Modul kini bertanya
   ke git sendiri: `git remote get-url --all origin` dan
   `git remote get-url --push --all origin`, dan SETIAP URL
   hasil wajib mengidentifikasi
   dianzherdiana25-hash/ACE. Target FETCH ikut digerbang
   (insteadOf dapat membelokkan sumber fetch sementara
   --push tetap ACE).
2. **Basis dari fetch yang dikontrol modul:** `git fetch
   origin +refs/heads/main:refs/ace-self-send/base` —
   refspec eksplisit ke ref milik modul; basis = OID ref
   itu. Probe peracunan (tracking ref berisi private.txt +
   refspec fetch terkonfigurasi tak memetakan main) kini
   menjadi tes: private.txt tidak terkirim dan ref
   teracun tidak pernah dikonsultasikan (nilainya utuh
   sesudah send).
3. **Setiap push** (isi, audit final, jalur gagal):
   `--no-follow-tags` + refspec penuh
   refs/heads/<branch>:refs/heads/<branch>. Tes real:
   push.followTags=true + tag teranotasi ber-canary rahasia
   — tag tidak meninggalkan mesin.
4. **Residual ditimbang, bukan disembunyikan:** penulisan
   payload/audit kini memakai O_NOFOLLOW (komponen akhir
   tak bisa ditukar symlink sesudah validasi). Penukaran
   komponen induk di antara cek dan buka tetap terbuka
   secara teoretis dan DITERIMA dengan alasannya: send
   berjalan di worktree terkontrol tanpa penulis konkuren
   dalam model ancaman. Allowlist nama berkas bukan
   pemindai rahasia isi — di luar cakupan amplop, dicatat.
   Pembungkus aplikasi tetap bukan pengganti scope token /
   ruleset sisi server; keputusan proteksi repo tetap di
   pemilik.

Yang terbukti membaik di putaran 3 tidak digeser (symlink
statis/terkomit tertolak sebelum tulis; finalisasi gagal ≠
sent; ack atomik, korup ditolak, hanya sesudah terverifikasi).
Penanda tetap ABSEN; gh auth tetap parkir menunggu
verifikasi putaran ini.
