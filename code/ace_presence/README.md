# EVO 0059 · Kehadiran

Modul lokal untuk dialog, waktu, dan kehadiran berbukti. Checkpoint ini
mencakup butir 1–40. Jurnal sesi adalah SQLite terisolasi dengan format
sendiri. Uji memakai workspace baru dan HTTP pada loopback.

| Butir | Modul | Bukti fixture |
| --- | --- | --- |
| 1 | `dialogue_server` | HTTP lokal, pergiliran, autentikasi, retry, dan verifikasi hash saat dibaca ulang. |
| 2 | `rolling_summary` | Petikan turn utuh dengan penunjuk sumber dan topik yang terlewat. |
| 3 | `conversation_memory` | Recall lintas sesi hanya dari ekspor yang diberi izin, bertambat, dan memenuhi retensi. |
| 4 | `persona_core` | Rantai versi persona dan bukti per perubahan, dengan identitas tetap. |
| 5 | `voice_channel` | Audio PCM yang sudah disediakan ditempatkan bergiliran ke dua kanal dengan interval berbasis sampel. |

| 6 | `owner_channel` | Antrean lokal memprioritaskan digest permintaan interupsi yang diizinkan. |
| 7 | `topic_tracker` | Setiap perubahan status perlu petikan yang cocok dengan turn. |
| 8 | `group_dialogue` | Giliran banyak peserta dengan persetujuan, aksi pass, dan hash per turn. |
| 9 | `bilingual_mirror` | Pasangan korpus ID–EN menjaga angka dan pasangan istilah eksplisit. |
| 10 | `promise_extractor` | Janji eksplisit orang pertama ID/EN, tanggal absolut, dan penunjuk turn. |
| 11 | `fact_corrector` | Usul koreksi dari kutipan sesi dan referensi pembanding terverifikasi. |
| 12 | `conversation_search` | Cari riwayat berizin dengan petikan bertambat dan ranking deterministik. |
| 13 | `session_handoff` | Tujuan, hash head, nonce, dan masa berlaku serah terima. |
| 14 | `clarification_asker` | Prioritas pertanyaan pada slot ambigu dengan biaya salah tertinggi. |
| 15 | `memory_writeback` | Kandidat fakta dengan bukti eksternal. Penulisan tertahan karena kelas event fakta sesi belum terdaftar. |

| 16 | `temporal_store` | Fakta berversi dengan batas tanggal setengah terbuka. |
| 17 | `calendar_engine` | Hari IANA meliputi transisi DST dan acara lintas batas. |
| 18 | `horizon_planner` | Tenggat antara dihitung mundur dari graf prasyarat. |
| 19 | `rhythm_learner` | Alokasi menit historis melintasi jam dan tengah malam. |
| 20 | `deadline_risk_forecaster` | Risiko dari durasi tercatat, dengan abstain pada sampel tipis. |
| 21 | `commitment_tracker` | Tenggat, peringatan, dan penyelesaian dengan bukti. |
| 22 | `fact_expiry_janitor` | Rencana kedaluwarsa mempertahankan fakta dengan hold. |
| 23 | `schedule_optimizer` | Pencarian jadwal yang meminimalkan biaya pindah dalam kandidat terbatas. |
| 24 | `moment_memory` | Recall peristiwa menurut topik, kedekatan tanggal, dan sumber. |
| 25 | `duration_estimator` | Median dan kuantil durasi dari analog dengan kompleksitas terdekat. |
| 26 | `workload_forecaster` | Beban menghitung irisan waktu menggunakan rasio eksak. |
| 27 | `quota_calendar` | Hari reset penyedia dengan zona eksplisit dan receipt pemakaian. |
| 28 | `dialogue_eval` | Evaluasi label recall serta petikan dan hash ringkasan. |
| 29 | `dialogue_replay` | Replay rentang sesi setelah verifikasi rantai utuh. |
| 30 | `time_bench` | Case, label terpisah, metode tetap, dan pelaporan salah ukur. |
| 31 | `speech_preference_memory` | Pilihan pembicara yang eksplisit, dengan tanggal berlaku. |
| 32 | `answer_length_adapter` | Blok wajib tetap utuh, pilihan lain mengikuti anggaran kanal. |
| 33 | `confusion_detector` | Pola frasa eksplisit ID/EN dengan penunjuk turn. |
| 34 | `summary_offerer` | Tawaran dibatasi perkembangan sesi dan jeda antartawaran. |
| 35 | `appointment_maker` | Draf janji dari irisan ketersediaan peserta. |
| 36 | `promise_reminder` | Pengingat deterministik dengan receipt untuk deduplikasi. |
| 37 | `dialogue_note_taker` | Petikan notulen terstruktur dari penanda pembicara berizin. |
| 38 | `thread_resumer` | Lanjutan paginasi dari hash riwayat terverifikasi. |
| 39 | `decision_marker` | Putusan berlabel, teratribusi, dan riwayat per ID. |
| 40 | `decision_linker_presence` | Tautan keputusan sah dan janji beserta sumber keduanya. |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_presence -t code -v
```
