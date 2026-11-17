# NOTA — Venv Verifikasi Rumah Kustodi Sandbox
## Menutup celah numpy tanpa menyentuh python sistem

Status: resep terverifikasi Ian, 2026-11-15 malam.
Konteks: konfirmasi suite penuh sandbox untuk PR #232
menemukan 8 error — semuanya `ModuleNotFoundError: numpy`
di python sistem sandbox (terbukti dari worktree pristine,
bukan regresi kode). Python sistem dan tenant lain TIDAK
disentuh; celahnya ditutup dengan venv khusus di rumah
Ian sendiri.

## Resep (persis seperti dijalankan)

```bash
cd ~/ace-work-ian                      # klon Ian di sandbox
python3 -m venv .venv-verify           # python sistem: 3.12.3
.venv-verify/bin/pip install --upgrade pip
.venv-verify/bin/pip install numpy     # terpasang: numpy==2.5.4
git worktree add ~/verify-main origin/main   # pohon bersih
cd ~/verify-main
PYTHONPATH=code ~/ace-work-ian/.venv-verify/bin/python -m unittest \
  ace_gnn.test_ast_embedder \
  ace_neurosymbolic.test_cegar_refinement \
  ace_neurosymbolic.test_graph_embedding \
  ace_neurosymbolic.test_neural_guided_search \
  ace_neurosymbolic.test_sketch_synthesizer \
  ace_autonomy.test_research_pipeline \
  ace_operational.test_autonomous_evolver \
  ace_operational.test_oaie_cli \
  ace_operational.test_ontological_godel_engine
```

## Hasil

**Ran 49 tests in 187.448s — OK** (15 Nov 2026 malam,
dari worktree bersih ~/verify-main di origin/main,
log sandbox ~/intake-logs/venv_verify.log).

Enam kelompok modul korban suite (gnn, neurosymbolic,
research pipeline, autonomous evolver, oaie_cli,
ontological godel) kini hijau di rumah kustodi. Dependensi
pihak ketiga yang benar-benar diimpor keenamnya hanya
numpy (7 situs impor langsung; tidak ada scipy/torch/
pandas di rantai impornya).

## Aturan pakai

- Verifikasi di sandbox selalu lewat venv ini; jangan
  `pip install` ke python sistem (itu wilayah operator
  dan tenant lain).
- Venv ini bisa dihapus dan dibangun ulang dari resep di
  atas; tidak ada state di dalamnya.
- Suite penuh tetap dijalankan dengan pola yang sama
  (PYTHONPATH=code + python venv ini) bila diperlukan.
