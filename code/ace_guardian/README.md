# EVO 0060 · Penjaga Diri

Paket lokal untuk kembaran, aturan aksi, dan pemulihan yang bisa
ditelaah. Fixture dibuat di direktori uji. Checkpoint mencakup butir 1–10.

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

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_guardian -t code -v
```
