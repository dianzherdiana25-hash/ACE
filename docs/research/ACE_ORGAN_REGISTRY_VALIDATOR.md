# Validator Konfigurasi & Registry Organ Multi-Brain (E1)

Dokumen rujukan untuk `tools/organ_registry_validate.py` (`ace.organ-registry-validate.v1`). Semua pemeriksaan dijalankan **strictly offline** tanpa panggilan HTTP dan tanpa memuat rahasia/kredensial.

## Skema yang Didukung

1. **`ace.organ-slate.v1`** (selaras §2.2–§2.4 `handover/RANCANGAN_EVO_0009.md`):
   - Memeriksa keberadaan kelima peran bridge/organ EVO 0009: `front`, `coder`, `validator`, `embedding`, dan `judge`.
   - Menegakkan status organ (`active`, `dismissed`, `declared-unavailable`, `standby`) serta fail-closed bila organ primer berstatus `dismissed` atau `declared-unavailable`.
   - Menegakkan **aturan heterogenitas**: proposer kode (`coder`) tidak boleh menunjuk organ identik dengan `validator`; pasangan bahasa yang memakai organ primer sama wajib menyatakan `rotation_partner` berbeda.
   - Mewajibkan `hold_on_exhaustion_in_measurement: true` pada peran `judge` serta angka anggaran integer positif (`bool` ditolak).
   - Memeriksa urutan rantai kontingensi pemilik (`nvidia` → `cloudflare` → `zai` → `cometapi`) dan menolak aktivasi diam-diam tanpa `registered_event_id`.
   - Memindai kebocoran token/API key (`sk-*`, `gsk_*`, `AIza*`, `Bearer *`) secara rekursif.

2. **`ace.brain_registry.v1`** (persistensi `code/ace_operational/brain_registry.py`):
   - Memeriksa status valid (`active`, `dismissed`, `declared-unavailable`), konsistensi log `events`, dan menolak `descriptor` kosong (penjaga atas bug wildcard `BrainRegistry.match`).

## Contoh Pemakaian CLI

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/organ_registry_validate.py --check-default --format markdown
PYTHONDONTWRITEBYTECODE=1 python3 tools/organ_registry_validate.py --print-template --output /tmp/slate.json
PYTHONDONTWRITEBYTECODE=1 python3 tools/organ_registry_validate.py --config /tmp/slate.json
```
