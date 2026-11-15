# REKAMAN INTAKE — Slate Otak v2 (Keputusan Pemilik 15 Nov 23:46 WIB)

Dieksekusi Ian, malam 15 Nov 2026. Dua GGUF baru terunduh
di rumah sandbox (`/workspace/ace-omega/models/`) dan
terverifikasi sha256 terhadap pin LFS Hugging Face
SEBELUM dipromosikan dari nama `.part`:

| Peran | Repo HF / berkas | Byte | sha256 (pin = terverifikasi) |
|---|---|---|---|
| Depan (MTP) :8001 | unsloth/Qwen3.5-4B-MTP-GGUF / Qwen3.5-4B-Q4_K_M.gguf | 2.834.975.040 | 3874209241c9a397e…b48a714e8630 |
| Coder :8002 | Qwen/Qwen2.5-Coder-7B-Instruct-GGUF / qwen2.5-coder-7b-instruct-q4_k_m.gguf | 4.683.073.536 | 509287f78cb4d4cf…5e963800894d3c |

Catatan nama: berkas MTP disimpan lokal sebagai
`Qwen3.5-4B-MTP-Q4_K_M.gguf` agar tidak menabrak berkas
fallback non-MTP (`Qwen3.5-4B-Q4_K_M.gguf`, 2.740.937.888 B,
sha 00fe7986…) yang nama HF-nya identik.

Sudah di rumah dari intake sebelumnya: bge-m3 Q8_0
(634.553.760 B, sha 950f4a8e…) untuk embedding :8003.
Organ on-demand: A3B (sudah dimiliki, konteks 8K) dan
Sahabat-AI-9B (belum diintake).

Status: TERINTAKE + TERVERIFIKASI — belum dimuat, belum
disajikan. Tahap berikutnya bench (MTP on/off via
llama-server untuk otak depan; coder; embedding smoke;
A3B -t 1 jangkar dengan disiplin jendela RAM), dilaporkan
ke hub sebelum service apa pun dinaikkan. Rekaman JSON
mesin: handover/stack_intake/INTAKE_V2_20261116.json.
