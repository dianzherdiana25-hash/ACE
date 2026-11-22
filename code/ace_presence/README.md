# EVO 0059 · Kehadiran

Modul lokal untuk dialog, waktu, dan kehadiran berbukti. Tabel menunjukkan cakupan butir 1–60 dan batas butir 15. Jurnal sesi adalah SQLite terisolasi dengan format
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
| 15 | `session_fact_candidates` | Kandidat fakta dengan bukti eksternal. Penulisan tertahan karena kelas event fakta sesi belum terdaftar. |

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
| 41 | `shared_history_answerer` | Petikan riwayat dengan permit dan partisipasi sumber. |
| 42 | `topic_boundary_guard` | Pagar kanal eksplisit dengan tinjauan untuk topik yang tidak dikenal. |
| 43 | `register_switcher` | Dua register mempertahankan slot fakta yang sama. |
| 44 | `dialogue_satisfaction` | Sinyal eksplisit dan jumlah turn tanpa rating. |
| 45 | `owner_rhythm` | Rata-rata durasi kalender kerja per hari lokal dengan provenance. |
| 46 | `best_time_advisor` | Saran bebas tabrakan dengan ranking dari riwayat fokus. |
| 47 | `topic_waitlist` | Daftar tunggu dengan aging, prasyarat, dan tanggal siap. |
| 48 | `recurring_reminder` | Jeda kalender lokal, verifikasi DST dan deduplikasi. |
| 49 | `daily_agenda` | Acara lokal dan daftar prioritas tenggat serta janji. |
| 50 | `weekly_review` | Tujuh hari dengan hasil, rencana, dan hambatan dipisahkan. |
| 51 | `deadline_collision` | Bukti defisit kapasitas preemptive di jendela tenggat. |
| 52 | `reschedule_proposer` | Kandidat pindah bebas tabrakan menurut jarak waktunya. |
| 53 | `estimate_calibrator` | Galat absolut, bias bertanda, dan kuantil rasio. |
| 54 | `day_archiver` | Manifest hari lokal tanpa menyalin isi turn. |
| 55 | `while_away_brief` | Kejadian bertanggal setelah checkpoint dengan cakupan. |
| 56 | `persona_continuity` | Pemeriksaan rantai antartahun dan drift nilai tetap. |
| 57 | `greeting_keeper` | Izin dan pencabutan sapaan dengan pilihan bawaan. |
| 58 | `presence_quality` | Cakupan respons dan rating per kanal serta abstain. |
| 59 | `smart_dnd` | Waktu tenang dengan interupsi yang diberi izin secara spesifik. |
| 60 | `presence_report` | Kohort tenggat dan bukti realisasi tepat waktu atau terlambat. |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_presence -t code -v
```

## Bench fixture tertutup

[Plan](fixtures/closed_presence/plan.json) menautkan ekspor rantai dialog,
label recall, serta kasus dan label waktu yang terpisah. Harness
`closed_bench.assess` menjalankan recall, ekstraksi janji, ringkasan
ekstraktif, audit, dan bench temporal dari input itu. [Run](fixtures/closed_presence/run.json)
mencatat 10/10 recall fakta atau janji terlabel, 9/9 petikan ringkasan cocok
byte dengan turn, dan 16/16 kasus temporal benar. Label hanya mewakili
fixture sintetis dengan kosa kata kueri yang telah diketahui. Login jaringan,
kanal suara langsung, dan terjemahan teks baru berada di luar bukti itu.

Flag `ACE_EVO0059_PRESENCE=1` menambahkan ringkasan bukti terverifikasi
ke hasil `step_mobile_report` bila plan di
`<workspace>/evo0059_presence/plan.json` cocok dengan
`ACE_EVO0059_PLAN_SHA256` dan semua sumber lulus verifikasi. Flag mati
secara bawaan. Program baca-saja untuk input ini.
