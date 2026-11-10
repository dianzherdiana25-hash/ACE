# Peta source ACE — snapshot 10 November 2026

Basis audit `52394dcf6f203197ffa66b2dc7f802c475690a63`. Seluruh 329 berkas Python diparse; 72.934 baris sebelum penambahan. Ada 48 direktori paket `ace_*`. Hubungan di bawah berasal dari impor AST, termasuk impor di dalam fungsi; bukan bukti seluruh jalur digunakan oleh daemon. File dan simbol beserta hash lengkap ada di [inventory](../../evidence/audit_20261110/source-inventory.json.gz).

| Modul | Fungsi nyata / batas interpretasi | Dependensi impor internal | Berkas / tes |
|---|---|---|---|
| `ace_abstract_interp` | Domain abstrak, invariant numerik dan disjungsi. | stdlib / lokal paket | 5 / 2 |
| `ace_abstraction` | Ekstraksi/pemakaian macro dari program; kelas bahasa tetap disediakan. | `ace_evolution` | 3 / 1 |
| `ace_automata` | Pembelajaran DFA L* dengan oracle ekuivalensi terbatas. | stdlib / lokal paket | 3 / 1 |
| `ace_autonomy` | Tujuan bertipe, broker alat, lease, budget dan escrow; pipeline riset juga berisi katalog topik tetap. | `ace_evolution`, `ace_mcts`, `ace_neurosymbolic`, `ace_runtime`, `ace_synthesis` | 15 / 3 |
| `ace_candidate_search` | AST aritmetika bertipe, pencarian, jurnal dan verifikasi. | stdlib / lokal paket | 8 / 2 |
| `ace_capability_evolution` | Pilot akuisisi, perubahan counter dan komposisi counter × DFA. | `ace_candidate_search`, `ace_research_primitives` | 9 / 3 |
| `ace_causal` | Penambangan hubungan kausal pada data/intervensi yang disediakan. | stdlib / lokal paket | 3 / 1 |
| `ace_chat` | Kontrak tugas simbolik data-only dari workflow ChatGPT/GitHub. | `ace_capability_evolution`, `ace_runtime` | 3 / 1 |
| `ace_code_agent` | Diagnosis masalah kode dan patch; jalur PR #94 hanya intake/diagnostik dan menahan promosi. | `ace_automata`, `ace_evaluator`, `ace_evolution` | 13 / 1 |
| `ace_cognition` | Telemetri perangkat, memori kesamaan token dan kurikulum buatan peneliti. Integrasi reasoning baru dicatat terpisah dari snapshot. | `ace_self_dev` | 7 / 3 |
| `ace_component_synthesis` | Sintesis AST komponen bertipe, forward valuation dan observational equivalence. | `ace_evolution` | 3 / 1 |
| `ace_conformal` | Prediksi interval/set dan pengendalian risiko dengan asumsi distribusinya. | stdlib / lokal paket | 3 / 1 |
| `ace_core_repair` | Doctor, admission, pustaka terurai dan konsistensi label drift yang terlihat. | stdlib / lokal paket | 6 / 1 |
| `ace_dsl_growth` | Solver BFS graf dan rasio 4:1 yang ditulis langsung; W4 bukan penemuan solver ini. | `ace_evaluator`, `ace_report` | 5 / 1 |
| `ace_egraph` | Equality saturation, rewrite dan ekstraksi berbiaya. | `ace_evolution` | 3 / 1 |
| `ace_epistemic` | Sampling ketidakpastian BALD pada himpunan hipotesis. | stdlib / lokal paket | 3 / 1 |
| `ace_evaluator` | Generator keluarga, seed evaluasi dan pemeriksaan anti-cheat. Seed rahasia bukan bukti independensi. | stdlib / lokal paket | 5 / 1 |
| `ace_evolution` | Island search, grammar berbobot dan optimasi Pareto. | `ace_dsl_growth` | 5 / 2 |
| `ace_game_theory` | Ko-evolusi minimax dua pemain. | stdlib / lokal paket | 3 / 1 |
| `ace_gnn` | Embedding AST/GNN Python; keberadaan layer tidak membuktikan pelatihan representasi yang berguna. | `ace_evolution` | 3 / 1 |
| `ace_host_controller` | Keputusan promosi, lineage, holdout, exposure ledger, pekerja subprocess dan watchdog. | stdlib / lokal paket | 18 / 4 |
| `ace_ilp` | Klausa relasional dan induksi aturan di atas knowledge base. | stdlib / lokal paket | 3 / 1 |
| `ace_integration_redteam` | Audit integrasi serta batas evaluator. | `ace_autonomy`, `ace_research_agenda`, `ace_research_generations`, `ace_research_repair`, `ace_runtime`, `ace_selfmodel` | 3 / 1 |
| `ace_interpolation` | Interpolan proposisional/linear dan invariant loop. | stdlib / lokal paket | 3 / 1 |
| `ace_inversion` | Lens dan transducer dua arah. | stdlib / lokal paket | 3 / 1 |
| `ace_loop` | Gene bertipe, mutasi dan rendering/kompilasi source internal terbatas. | stdlib / lokal paket | 3 / 1 |
| `ace_mcts` | Pencarian UCT atas templat AST terbatas; bukan planner dunia umum. | `ace_evolution` | 3 / 1 |
| `ace_mission` | Schema misi, antrean SQLite, generator misi dan proposer. | `ace_automata`, `ace_evolution` | 6 / 1 |
| `ace_neurosymbolic` | A* berpemandu fitur statistik, sketch, CEGAR dan representasi graf. | `ace_dsl_growth`, `ace_evolution` | 9 / 4 |
| `ace_pac_bayes` | Batas generalisasi PAC-Bayes dengan prasyarat prior dan sampel. | stdlib / lokal paket | 3 / 1 |
| `ace_real_world` | Parser log, data wrangling, Git/network/tool synthesis dan sentinel. | `ace_mission` | 9 / 1 |
| `ace_red_team` | Fuzzer, poisoning dan serangan kompleksitas. | stdlib / lokal paket | 3 / 1 |
| `ace_report` | Ringkasan bahasa Indonesia untuk HP. | stdlib / lokal paket | 3 / 1 |
| `ace_research_agenda` | Pemilihan gap, hipotesis, anggaran kampanye dan pemulihan antarproses. | `ace_autonomy`, `ace_research_generations`, `ace_research_repair`, `ace_runtime`, `ace_selfmodel` | 6 / 2 |
| `ace_research_discovery` | DSL pohon/Dyck, abstraksi dari sumber dan adapter transfer. | `ace_research_primitives`, `ace_runtime` | 10 / 1 |
| `ace_research_f12` | Probe diskriminatif dan koordinator riset kausal dalam kelas hipotesis. | `ace_host_controller`, `ace_runtime` | 7 / 1 |
| `ace_research_f13` | Abstraksi memori kausal dan eksperimen prior pencarian. | `ace_host_controller` | 7 / 1 |
| `ace_research_f14` | Diagnosis error dan pencarian komposisi dalam katalog AST mekanisme. | `ace_host_controller`, `ace_research_f12` | 10 / 1 |
| `ace_research_generations` | Mekanisme fitur, lineage dan benchmark pertumbuhan generasi. | `ace_autonomy`, `ace_research_primitives`, `ace_runtime`, `ace_selfmodel` | 12 / 2 |
| `ace_research_hypgen` | F10 hipotesis bertipe dan pembanding katalog/acak/extra-compute. | `ace_runtime` | 7 / 1 |
| `ace_research_primitives` | R1 RPNI dan bank DFA publik. | stdlib / lokal paket | 3 / 1 |
| `ace_research_repair` | Korpus bug, representasi kegagalan, operator patch, memori dan pengujian staging. | `ace_research_primitives`, `ace_runtime` | 12 / 2 |
| `ace_research_reptransfer` | R9 fitur okupansi state DFA dan adapter target. | `ace_research_primitives` | 12 / 2 |
| `ace_runtime` | Akuisisi tugas a/b, registry program, SQLite WAL dan replay. | `ace_candidate_search`, `ace_capability_evolution`, `ace_core_repair`, `ace_mission`, `ace_research_primitives` | 5 / 2 |
| `ace_self_dev` | Koordinator siklus, diagnosis, mutasi gene, stagnasi, metakognisi dan checkpoint. | `ace_host_controller`, `ace_loop` | 30 / 6 |
| `ace_selfmodel` | Introspeksi state, pengalaman, prediksi metakognitif dan refleksi. | `ace_autonomy`, `ace_runtime` | 7 / 1 |
| `ace_smt` | DPLL(T), kendala linear dan verifier program kecil; kelulusan contoh bukan bukti soundness universal. | stdlib / lokal paket | 3 / 1 |
| `ace_synthesis` | CEGIS di atas evolutionary island search. | `ace_evolution` | 3 / 1 |

## Entrypoint di luar paket

| Entrypoint | Jalur dan temuan |
|---|---|
| `ace.py` | CLI runtime, misi dan alat; enqueue/run/predict/evaluate beroperasi pada kontrak domain tertentu. |
| `autonomy.py` | CLI autonomy; workspace terpisah dari contoh runtime. |
| `auto_curriculum.py` | Mengurutkan tugas katalog dan menyimpan model; bukan agenda riset terbuka. |
| `ace_self_evolver.py` | Dapat commit dan push `main`; bukan perintah uji aman pada instalasi aktif. Tidak dijalankan saat audit. |
| `tools/ace_autonomous_daemon.py` | Menghubungkan researcher/parameter cycle, telemetry, watchdog dan git auto-push; batas intake PR #94 belum menyatukan gate semua entrypoint. |
| `tools/ace_mission_worker.py` | Menetapkan `ACCEPTED` dan alasan hasil sebelum evaluasi perilaku; reproduksi negatif disimpan. |
| `tools/ace_mobile_dashboard.py` | Membaca heartbeat dan konsultasi; bukan bukti provider sedang online. |
| `install.sh` | Installer; tidak dijalankan atau diterapkan ke HP. |
| `tools/ace_reasoning.py` (baru) | Integrasi opt-in Problem → solver komponen → verifikasi → memori yang dapat dijalankan lagi. |

## Cakupan pengujian

463 tes dari harness utama, 135 tes tambahan dari seluruh file tes paket yang terlewat harness, 12 tes reasoning baru, dan 8 tes tools receipt: 618 kasus berbeda, tanpa menjumlahkan ulang 10 tes solver yang juga dijalankan bersama tes baru. Cabang historis tidak dicampur ke dalam jumlah ini. Validasi eksternal ilmiah tetap NOT_ASSESSED.
