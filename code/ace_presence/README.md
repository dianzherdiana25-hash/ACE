# EVO 0059 · Kehadiran

Modul lokal untuk dialog, waktu, dan kehadiran berbukti. Checkpoint ini
mencakup butir 1–5. Jurnal sesi adalah SQLite terisolasi dengan format
sendiri. Uji memakai workspace baru dan HTTP pada loopback.

| Butir | Modul | Bukti fixture |
| --- | --- | --- |
| 1 | `dialogue_server` | HTTP lokal, pergiliran, autentikasi, retry, dan verifikasi hash saat dibaca ulang. |
| 2 | `rolling_summary` | Petikan turn utuh dengan penunjuk sumber dan topik yang terlewat. |
| 3 | `conversation_memory` | Recall lintas sesi hanya dari ekspor yang diberi izin, bertambat, dan memenuhi retensi. |
| 4 | `persona_core` | Rantai versi persona dan bukti per perubahan, dengan identitas tetap. |
| 5 | `voice_channel` | Audio PCM yang sudah disediakan ditempatkan bergiliran ke dua kanal dengan interval berbasis sampel. |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_presence -t code -v
```
