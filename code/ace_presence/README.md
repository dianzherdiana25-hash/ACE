# EVO 0059 · Kehadiran

Modul lokal untuk dialog, waktu, dan kehadiran berbukti. Checkpoint ini
mencakup butir 1–15. Jurnal sesi adalah SQLite terisolasi dengan format
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

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_presence -t code -v
```
