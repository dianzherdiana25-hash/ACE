# EVO 0051 · Deliberasi dan ramalan

Draf parsial dari `main` `42f0102`. Tabel memuat pasangan program dan verifier
yang ada di paket ini. Angka butir mengikuti rancangan EVO 0051.

| Butir | Program | Pemeriksaan fixture |
|---:|---|---|
| 1 | `debate_protocol.py` | Replay giliran dan anggaran, sanggahan, putusan terlacak |
| 2 | `dissent_ledger.py` | Penulis serentak, append putusan, perubahan dan pemotongan relatif checkpoint |
| 3 | `devil_advocate.py` | Hilangnya keluarga sumber dan perubahan asumsi mengubah margin |
| 4 | `consensus_detector.py` | Ballot privat dan publik, denominator, indikator yang memerlukan review |
| 5 | `precedent_memory.py` | Pencarian per tanggal, pemecah seri, kondisi, preseden dengan outcome berbeda |
| 6 | `argument_graph.py` | Sisi bersumber, jalur, dan komponen kuat tanpa rekursi |
| 7 | `evidence_weigher.py` | Bobot eksak per keluarga, bukti berlawanan, sumber belum terverifikasi |
| 8 | `cross_examination.py` | Pertanyaan, penundaan, jawaban bersumber, dan konsesi per klaim |
| 9 | `fallacy_detector.py` | Countermodel logika proposisional dan premis kontradiktif |
| 10 | `steelman_generator.py` | Jalur dukungan terkuat dan pemilihan keluarga independen |
| 11 | `minority_report.py` | Posisi, sanggahan luar kelompok, dan tanggapan dalam transcript |
| 12 | `decision_brief.py` | Replay transcript, indeks dasar putusan, dissent, dan preseden |
| 13 | `moderator.py` | Giliran, rujukan agenda wajib, dan tenggat inklusif |
| 14 | `role_rotation.py` | Penugasan minimum, eligibilitas, riwayat, dan pemecah seri |
| 15 | `anonymous_round.py` | Token per ronde, batas kuorum, dan transcript tanpa roster |
| 16 | `expert_panel.py` | Cakupan topik, konflik, masa berlaku, kapasitas dan anggaran |
| 17 | `conflict_mapper.py` | Jalur kepentingan bertanggal dan tumpang tindih pihak |
| 18 | `synthesis_engine.py` | Grounded labeling, bukti diakui, serta rekomendasi atau tunda |
| 19 | `appeal_protocol.py` | Bukti baru, review independen, dan riwayat putusan asal |
| 20 | `emergency_decision.py` | Putusan sementara, review terikat hash, dan kedaluwarsa |
| 21 | `quorum_engine.py` | Kelas masalah, peran, pembulatan, penarikan, dan sumber kehadiran |
| 22 | `deliberation_scheduler.py` | Optimasi urgensi dengan tenggat dan kredit internal |
| 23 | `forecaster.py` | Odds Bayesian, rentang skenario, dan dampak satu sumber dihapus |
| 24 | `prediction_ledger.py` | Riwayat versi, batas ramalan, resolusi, dan checkpoint |
| 25 | `brier_scorer.py` | Brier berpasangan, baseline laju dasar, dan kontrol urutan waktu |
| 26 | `calibration_analyzer.py` | ECE, bin kosong, reliabilitas, dan grafik SVG |
| 27 | `scenario_generator.py` | Pohon peluang eksak, pengamatan bersarang dan payoff |
| 28 | `signal_watcher.py` | Sampel beruntun, hysteresis, kedaluwarsa dan bukti |
| 29 | `forecast_aggregator.py` | Bobot per keluarga, log-odds dan sensitivitas |
| 30 | `decision_linker.py` | Versi yang dirujuk, ambang dan daftar putusan terdampak |
| 31 | `source_credibility.py` | Penilaian per topik, umur bukti, dan satu kontribusi per klaim |
| 32 | `weighted_voting.py` | Bobot keahlian, kuorum, transfer preferensi dan seri |
| 33 | `async_deliberation.py` | Buffer lintas siklus, deadline dan replay checkpoint |
| 34 | `voi_limiter.py` | Posterior per hasil uji, nilai informasi bersih dan anggaran |
| 35 | `disagreement_map.py` | Matriks posisi berbobot, abstain, data hilang dan SVG |
| 36 | `worst_case_test.py` | Payoff worst-case, maximin, regret dan dominasi |
| 37 | `argument_scorer.py` | Median rubrik, rentang observasi, kuorum dan kriteria kritis |
| 38 | `circular_detector.py` | Fondasi independen, aturan multipremis dan saksi siklus residual |
| 39 | `deadlock_breaker.py` | Pola distribusi berulang, jeda, pemulihan dan provenance |
| 40 | `expert_witness.py` | Undangan lokal terikat hash dan testimoni dalam jendela |
| 41 | `claim_timeline.py` | Versi klaim bertanggal dan diff yang menyertakan perubahan antara |
| 42 | `position_drift.py` | Drift individu, variasi distribusi dan peserta pembanding |
| 43 | `dual_brief.py` | Dua format, glosarium bersumber dan angka literal terjaga |
| 44 | `debate_archiver.py` | Paket preseden kanonis, lesson, manifest dan hash eksternal |

| 45 | `method_tournament.py` | Matriks berpasangan, peringkat, biaya dan sensitivitas keluarkan satu kasus |
| 46 | `reference_class.py` | Kelas pembanding, cutoff, fallback dan kontras di luar kelas |
| 47 | `question_decomposer.py` | Saksi logis, subpertanyaan berulang dan peluang bersyarat |
| 48 | `hybrid_forecast.py` | Bobot Brier eksak, ketersediaan sumber, dan diagnosis leave-one-out |

Butir tersisa pada 0051 mencakup 49–60. Pengukuran
di paket ini memakai fixture sintetis. Pasangan program dan tes yang
tercantum dihitung bersama untuk rentang baris per kemampuan. Verifier
ambang dan langkah integrasi berada di luar hitungan kemampuan.

## Jalankan verifier

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_deliberation -t code -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -q ace_operational.test_leap_wiring
```

Program menerima JSON lokal melalui `python3 -m ace_deliberation.<modul>`.
Jalankan `--help` untuk opsi masing-masing. Berkas `test_<modul>.py` memuat
contoh masukan kecil yang juga dipakai dalam pemeriksaan hasil. Ledger
dissent menerima event melalui subperintah `append` dan `audit`.
Simpan checkpoint yang tepercaya di luar ledger untuk mendeteksi
hilangnya bagian riwayat. Pemeriksaan hash membuktikan konsistensi byte
relatif terhadap checkpoint. Identitas penulis memerlukan bukti tersendiri.

Kurva kalibrasi bisa diekspor sebagai SVG dengan `--format svg`. Brier
memakai probabilitas desimal tersimpan, sedangkan forecaster juga
menerbitkan pecahan persisnya. Angka laju dasar dihitung dari resolusi
sebelum cut-off dan pertanyaan held-out yang berbeda.

## Ambang EVO

`verify_bench.py` menerima JSON berisi `paired_decisions` dan `brier_input`.
Setiap pasangan menyertakan penilaian dari luar pada skala 0–100, rujukan
putusan serta penilaiannya, dan masukan brief untuk lengan deliberasi.
Pemeriksaan membandingkan rerata delta dengan 10 poin, membandingkan Brier
secara ketat dengan baseline laju dasar, dan memeriksa apakah setiap
putusan memiliki preseden yang memenuhi kondisi. Bukti fixture
memeriksa ketiga rumus dan batasnya. Pengukuran kemampuan EVO menunggu
putusan kedua lengan yang dinilai secara independen dan resolusi held-out
yang dapat diperiksa.

## Langkah integrasi

`step_self` menyediakan langkah `step_evo0051_deliberation` ketika
`ACE_EVO0051_DELIBERATION=1`. Nilai bawaan mematikan langkah. Saat aktif
langkah membaca `evo0051_deliberation_input.json` dari workspace fixture
atau workspace operator yang menyediakan berkas tersebut. Satu input
brief yang dapat diputar ulang dan memiliki preseden menghasilkan status
`reviewable` dan hash input untuk penelaahan. Berkas yang hilang, rusak,
symlink, atau tidak memiliki preseden tidak menghasilkan status siap ditelaah.
Langkah ini mengembalikan ringkasan pada pemanggil tanpa menulis store
atau melakukan putusan.

`leap_wiring.py` di basis juga memakai label EVO 0051 untuk pemeriksa
kesehatan lama. Langkah deliberasi memakai flag tersendiri.
