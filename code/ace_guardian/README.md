# EVO 0060 · Penjaga Diri

Paket lokal untuk kembaran, aturan aksi, dan pemulihan yang bisa
ditelaah. Fixture dibuat di direktori uji. Tabel mencakup butir 1–60.

| Butir | Modul | Verifikasi fixture |
| --- | --- | --- |
| 1 | `state_forker` | Salinan inode terpisah, menolak symlink dan tujuan di dalam sumber. |
| 2 | `twin_runner` | Siklus dengan operasi data tertutup, memblokir perubahan field beku. |
| 3 | `twin_diff` | Jejak mulai sama, delta per field, penunjuk siklus berbeda pertama. |
| 4 | `counterfactual_protocol` | Satu operand berubah, dua lengan dengan seal deterministik. |
| 5 | `twin_chaos` | Fault sebelum atau sesudah commit fixture, replay dari hash checkpoint. |
| 6 | `promotion_gate` | Ambang bertanda per metrik, hold jika bukti sama atau skor lebih buruk. |
| 7 | `rollback_engine` | Salinan pemulihan ke tujuan fixture baru, sumber lama diverifikasi ulang. |
| 8 | `twin_registry` | Transisi dan rantai event terkait ke manifest awal. |
| 9 | `migration_rehearsal` | Kapasitas, bentuk JSON, dan byte salinan tujuan. |
| 10 | `snapshot_scheduler` | Slot deterministik, batas catch-up, retensi, dan receipt deduplikasi. |
| 11 | `incremental_fork` | Pakailah ulang byte dengan hash yang cocok, lalu verifikasi inode sumber dan tujuan terpisah. |
| 12 | `resource_guardian` | Alokasi lintas kembaran dan pelanggaran RAM/CPU pada jejak terurut. |
| 13 | `fork_redactor` | Pointer eksplisit dan pola nama field disunting di salinan fixture. |
| 14 | `promotion_dossier` | Setiap rujukan scorecard dibaca dan dicocokkan ke hash penopang. |
| 15 | `rule_dsl` | Grammar deklaratif bertipe dan pesan diagnostik per baris. |
| 16 | `rule_compiler` | Kompilasi katalog aksi, tipe kondisi, urutan deny/review/allow, dan digest. |
| 17 | `action_gate` | Kelas terdaftar dan bentuk fakta lengkap diperlukan supaya aturan dapat berlaku. |
| 18 | `custody_rules` | Pagar aksi eksternal, perubahan beku, uang, merge, dan memory dalam DSL fixture. |
| 19 | `gate_receipt_ledger` | Rantai receipt, pendeteksian perubahan, dan replay identik. |
| 20 | `rule_simulator` | Perbandingan hasil dua kebijakan atas riwayat yang sama. |
| 21 | `adversarial_rule_tests` | Kasus produk domain fixture menunjukkan saat invarian gagal. |
| 22 | `exception_manager` | Pengecualian review terikat permintaan, kebijakan, persetujuan, dan TTL. |
| 23 | `rule_change_protocol` | Parent yang tepat, versi baru, seluruh kelas, dan label regresi. |
| 24 | `compliance_reporter` | Receipt cocok dengan waktu dan hash permintaan; gap dilaporkan. |
| 25 | `coverage_checker` | Bedakan kelas tidak terdaftar dari outcome yang belum diuji. |
| 26 | `house_supervisor` | Heartbeat lokal dengan usia, nama komponen, status, dan urutan lokalisasi. |
| 27 | `recovery_playbooks` | Jalur pemulihan tetap, copy fixture, checksum sumber dan tujuan. |
| 28 | `incident_journal` | Kegagalan tetap tercatat setelah insiden ditutup. |
| 29 | `confidence_ledger` | Prediksi sebelum resolusi dengan bukti terpisah dan rantai hash. |
| 30 | `calibration_scorer` | ECE dan Brier berbobot per domain dengan basis point dan rasio eksak. |
| 31 | `recovery_drill` | Hentikan subprocess fixture yang baru diluncurkan dan ukur waktu sampai restore terverifikasi. |
| 32 | `leak_detector` | Median kemiringan RSS per instance, tahan efek satu outlier. |
| 33 | `orphan_sweeper` | Tentukan file tua tak terujuk tanpa melakukan penghapusan. |
| 34 | `store_verifier` | Checksum, berkas hilang, dan inventory tambahan. |
| 35 | `log_rotator` | Pecah log fixture dan verifikasi isi dari gzip deterministik. |
| 36 | `organ_health_report` | Umur, streak, rasio, dan data health yang belum ada. |
| 37 | `slow_step_trend` | Median dua jendela dan delta dengan denominator. |
| 38 | `step_quarantine` | Usulan karantina berprovenance dengan daftar fungsi wajib. |
| 39 | `cycle_budget_guard` | Cadangan untuk langkah wajib dan defer yang tidak memakai jatah. |
| 40 | `state_of_ace` | Ringkasan satu halaman dari panel bertambat. |
| 41 | `safe_mode` | Latch anomali, syarat bersih, dan persetujuan untuk kembali normal. |
| 42 | `gate_regression_runner` | Verifikasi keputusan beserta aturan pertama dan cakupan kelas. |
| 43 | `trusted_actor_admin` | Grant, expiry dan pencabutan per scope dengan sumber otoritas. |
| 44 | `action_anomaly` | Deteksi aktor baru dan kuantitas outlier terhadap baseline. |
| 45 | `self_compliance_score` | Skor pekanan dengan denominator termasuk receipt yang hilang. |
| 46 | `snapshot_retention` | Rencana retensi mematuhi hold, umur, dan batas byte. |
| 47 | `rollback_drill` | Bandingkan hasil restore nyata fixture terhadap delta yang diharapkan. |
| 48 | `standby_mirror` | Audit urutan dan hubungan manifest replika sebelum tinjauan failover. |
| 49 | `recovery_time_tracker` | Waktu deteksi/pulih serta insiden tidak tuntas. |
| 50 | `postmortem_writer` | Timeline dan hipotesis berujukan tanpa menyimpulkan akar sebab. |
| 51 | `abstention_calibrator` | Kurva selective risk dengan ambang dan minimum sampel. |
| 52 | `calibration_to_director` | Saran abstain atas confidence domain yang bertambat. |
| 53 | `ece_publisher` | Tabel lokal ECE dan cakupan domain dari ledger resolusi. |
| 54 | `low_confidence_registry` | Abstain untuk pengukuran kedaluwarsa atau tipis. |
| 55 | `report_truth_checker` | Verifikasi pointer JSON, hash sumber, dan jenis nilai klaim. |
| 56 | `decade_verdict_board` | Tampilkan status tercatat dan sumber belum terverifikasi. |
| 57 | `flag_transition_manager` | Usulan versi flag dengan bukti terbaru dan draf rollback. |
| 58 | `decade_baseline_archiver` | Tar+gzip byte-identik dengan metadata tetap dan isi bertambat. |
| 59 | `decade_closing_report` | Pisahkan bukti fixture dari penerimaan yang terdaftar. |
| 60 | `next_decade_opener` | Tranche usulan berdasarkan kesenjangan dengan bukti dan uji. |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_guardian -t code -v
```
