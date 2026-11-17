# AUDIT PENYERAPAN BELAJAR — Inventaris + Klasifikasi (DRAF untuk hub)

Operator: Ian, 2026-11-15 malam. Sumber inventaris:
`/workspace/ACE/.ace_evolution` (44 berkas, 1,8 MB — state
lini Antigravity di sandbox), `/workspace/ace-workspace/`
(status engine + cognitive_memory — rumah runtime engine,
LIVE, hanya dibaca), repo ACE main @77cca3c (cek sampel via
clone sandbox ~/ace-work-ian), dan paket-paket bukti di
GitHub. Kelas: (a) sudah terhubung ke perilaku aktif,
(b) layak + bisa dihubungkan, (c) trivial/tidak layak
dihubungkan sebagai kode.

## Angka jujur di muka

- Ledger belajar yang TER-RATIFIKASI: 5 entri / 3 misi
  berbeda (0001 ×3 entri duplikat, 0001b, 0002).
- Isi ingatan kognitif (mission 0002): **2 entri seed** —
  keduanya catatan operator, nol hasil belajar tertulis.
- Penghitung "siklus" engine (533 tick pada 22:40, naik
  ±1/10 dtk) BUKAN ukuran belajar; generation_seq evolusi = 1.
- Di luar 3 misi, TIDAK ditemukan kandidat kode siklus
  evolusi yang pernah mendarat di pohon aktif.

## Tabel klasifikasi

| # | Keluaran | Kelas | Bukti / alasan |
|---|---|---|---|
| 1 | Kode misi 0001/0001b/0002 (dari ratified_history: autonomous_engine, language, speech_acquisition, story_projector, web_server, ace_indo_nlp/*) | **(a)** | Berkas-berkas itu ada di main + tesnya; perilaku aktif ACE memang memakainya. |
| 2 | Mekanisme ingatan kognitif mission 0002 | **(a) mekanisme; ISI = temuan** | Kode terhubung (web_server/memory store di main); isinya berhenti di 2 entri seed — engine tidak pernah menulis hasil belajarnya ke sana. Lihat kandidat #8. |
| 3 | Eksperimen compositional OAIE + vonis COMPOSITIONAL_OAIE_VERIFIED (falsification probes lulus; honesty_boundary tertulis) | **(a) mekanisme** | Modul compositional_oaie.py di main, dirujuk autonomous_evolver / evolution_mission_loop / oaie_cli / oaie_unlimited. |
| 4 | 14 berkas synthesized_skills (g1–g4, primitif typed: abs_diff dari bounded_margin, dst.) | **(c)** | Artefak keluaran eksperimen #3 — fungsi primitif trivial; nilai mereka evidensier (catatan eksperimen), bukan kode yang layak diimpor. Mesin sudah melakukan reuse-nya di dalam eksperimen. |
| 5 | Temuan HIGH backlog: `sovereign_runtime.py` fallback `{"verified": True}` tanpa executor (baris ±517) | **(b) UNGGULAN** | TERVERIFIKASI masih ada di main @77cca3c (clone sandbox, jendela 510–522). Engine mendiagnosis bug kejujuran pada dirinya sendiri — dan diagnosisnya tidak pernah dieksekusi. |
| 6 | EVOLUTION_WORK_ORDER (generation_seq 1, goal = persis temuan #5, acceptance: test_sovereign_runtime + verify_sources; salinan sama di runtime/ACE_WORK_ORDER.json) | **(b)** | Work order engine sendiri, belum dieksekusi. Eksekusi = perbaiki #5 fail-closed + cek penerimaannya, via draft PR. |
| 7 | 20 temuan silent_except_pass di backlog | **(b) sebagai kelas, berbatas** | Sampel TERVERIFIKASI nyata di main: substrate_guardian.py:68-69, 81-82 `except Exception: pass`. Tiap instans dinilai sendiri: yang menelan error di jalur verifikasi diperbaiki; yang memang best-effort diberi alasan tercatat. |
| 8 | Jalur tulis engine → ingatan kognitif (menghubungkan keluaran siklus ke memory store mission 0002) | **(b) kandidat desain** | Menjawab temuan #2. Perlu rancangan dulu (skema record apa yang layak disimpan; jangan menulis tick noise). Keyakinan sedang — desain mendahului kode. |
| 9 | Sisa backlog: 149 complex_function + 137 missing_unit_test + 5 missing_module_docstring + 1 oaie_high_search_cost (dari 313 temuan / 430 berkas) | **(c)** | Kelas lint; memperbaikinya massal = gerak, bukan penyerapan. Register saja. |
| 10 | Spore/DAG/checkpoint kontinuitas (evolution_spore, substrate_spore, stigmergic_dag ×2, runtime_checkpoint ×2, continuity_probe) | **(c) untuk penghubungan kode** | Ini STATE mekanisme kontinuitas (mekanismenya sendiri kode di main = (a) sebagai mekanisme); instans state bukan kode — rumah persistennya = paket audit ini di GitHub. |
| 11 | Keluaran lab bahasa/practice engine (morfologi_imbuhan.py, practice_cycle_*.py — terlihat hidup ±21:19) | **PROVISIONAL (c)** | Lokasi tidak ditemukan pada sapuan /workspace/ACE + ace-workspace + ace-work malam ini; status engine menunjukkan track bahasa aktif dengan vocab_added 0 pada siklus terakhir. Konfirmasi lokasi + sampel 2 berkas sebelum klasifikasi final. |
| 12 | **Lineage guard → perilaku baku solver (default-on)** | **(b) JALUR CEPAT** | Lisensi: vonis GUARD_ADOPTED tersegel (PR #230). Rancangan aktivasi di bawah. |

## Rancangan aktivasi kandidat #12 (guard default-on)

1. Titik sambung: solver produksi di repo (solve_task_param
   di jalur solver grid v3) menerima port persis tiga
   sisipan B.2 dari solve_task_guarded (PR #193): peta label
   first-generation-wins, hook guard satu-slot BASE pada
   konstruksi frontier, perekam jangkar ace.lineage_anchor.v1.
2. Saklar: flag guard dengan baku ON untuk konstruksi
   frontier; OFF harus mereproduksi perilaku stock persis.
3. Gerbang regresi wajib di PR-nya: (i) tes identitas gaya
   L4 — guard OFF == stock byte-identik pada saksi 020/021;
   (ii) baterai inokulasi langkah-4 sebagai tes (stock
   SUSCEPTIBLE, guarded NOT_SUSCEPTIBLE, anchor
   NO_REGRESSION); (iii) seluruh suite tes repo hijau;
   (iv) harness konfirmasi TIDAK diubah — ia tetap alat ukur
   eksternal.
4. Bentuk: draft PR, tanpa merge; dihitung "terserap" hanya
   sesudah ratifikasi independen hub, sesuai aturan tata
   kelola Q4 (PR #228).

## Usulan urutan eksekusi kelas (b)

1. #12 guard default-on (jalur cepat — lisensi vonis segar).
2. #5+#6 sovereign_runtime fail-closed (work order engine
   sendiri; acceptance sudah tertulis oleh engine).
3. #7 silent_except_pass (kelas berbatas, per-instans).
4. #8 desain jalur tulis ingatan (desain dulu, hub menilai).

*Catatan cakupan: inventaris ini mencakup state sandbox +
repo; state .ace_evolution salinan VM tidak ditemukan
selain worktree riset (PR #189/#192/#193 — paket bukti,
sudah di GitHub). DB operasional engine (ace_operational.
sqlite3, live) tidak dibedah malam ini — isinya state
runtime, bukan artefak belajar; dicatat sebagai register.*
