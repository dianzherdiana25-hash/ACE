# ACE Ω — Addendum 22, 2026-11-12: Integrasi Workflow → Sandbox v2; OMEGA-03 Berhenti di Gerbang RAM

PR #124 (draft, bertumpuk di atas #123).

**Integrasi selesai.** `LocalRepoWorkflow` kini ber-sandbox bawaan
v2 (mundur ke backend bwrap hanya bila v2 tak dapat dibangun;
keduanya fail-closed). Test pengabelan baru menguncinya; sapuan
penuh 214 test OK.

**Jalan ulang OMEGA-03 lewat jalur resmi** (bukti:
`evidence/omega03_rerun_v2sandbox.json`): workflow melewati titik
berhenti Fase 1 — baseline kini *tereksekusi* di dalam isolasi
sungguhan dan mengembalikan FAIL yang jujur untuk fixture buggy
(Fase 1: BLOCKED_ENVIRONMENT, tidak ada eksekusi sama sekali).
Itu kemajuan terukur dari integrasi ini.

Run kemudian berhenti di gerbang inferensi dengan `NO_LOCAL_MODEL`:
admission RAM router (fitur keselamatan Fase 1, bekerja sesuai
desain) menolak 8B karena host saat ini melaporkan hanya ~0,6 GB
RAM tersedia melawan estimasi 5,4 GB. Memori itu tertahan di luar
pandangan proses VM ini dan tidak dapat dibebaskan dari dalam
(drop_caches read-only); model 3B (estimasi 2,3 GB) pun di atas
garis. **Tidak ada klaim LOCALLY_VERIFIED** — menyelesaikan verdict
itu adalah pengulangan di host yang lebih lega, bukan kode baru.
Item ini tetap terbuka secara eksplisit di antrean direktur,
termasuk siklus direktur #3 yang berbagi gerbang RAM yang sama.
