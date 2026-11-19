# Gelombang tepi loop dan agenda WS-9

Probe offline pada basis `95cee12` menemukan bahwa agenda kosong memilih
sebuah ID bawaan yang tidak ada dalam masukan. Delta ini mengembalikan
`SEARCH_SPACE_EXHAUSTED` beserta seed yang dapat diulang untuk kondisi
tersebut. Tes mencakup gerbang siklus, batas jadwal audit, restart cursor,
masukan rusak, kontrak skor, dan write-back gagal pada store sementara.

```sh
PYTHONPATH=code:. python3 -m unittest ace_operational.test_loop_boundary_wave ace_operational.test_ratification_loop ace_operational.test_memory_writeback ace_self_dev.test_self_dev_loop.TestSelfDevelopmentLoop.test_agenda_engine_avoids_repeated_falsified_mutations -q
```

SELESAI — 46 tes lulus, termasuk 12 kasus baru di
[test_loop_boundary_wave.py](../../code/ace_operational/test_loop_boundary_wave.py).
Kasus agenda kosong gagal sebelum perbaikan.

TERSISA — keputusan kebijakan untuk penanganan episode yang gagal sementara.
`execute_ratification_step` memajukan cursor untuk setiap hasil yang
dikembalikan, termasuk hasil `BrainUnavailable`. Pembaruan cursor dan event
store merupakan panggilan terpisah. Usulan isi ulang berupa tes crash di
antara kedua panggilan dan aturan retry yang diratifikasi.

PENGHAMBAT — ambang numerik syarat berdiri seluruh modul TIDAK TAHU. Perintah
tes di atas memberi bukti untuk kasus terdaftar dengan chat tiruan dan tanpa
menyatakan cakupan menyeluruh.
