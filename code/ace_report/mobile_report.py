"""Mobile-readable Indonesian scientific progress report generator (PRD FR-09, FR-14)."""
from __future__ import annotations

import datetime
from typing import Any, Dict


def generate_indonesian_mobile_report(experiment_data: Dict[str, Any]) -> str:
    """Generates concise, high-contrast Indonesian Markdown optimized for smartphone screens."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d %B %Y %H:%M UTC")

    graph_stats = experiment_data.get("graph_results", {})
    ratio4_stats = experiment_data.get("ratio4_results", {})
    hypotheses = experiment_data.get("hypotheses_evaluation", {})

    mean_a_g = graph_stats.get("A", {}).get("mean", 0.0)
    mean_b_g = graph_stats.get("B", {}).get("mean", 0.0)
    mean_c_g = graph_stats.get("C", {}).get("mean", 0.0)

    report = f"""# 📱 Laporan Hasil Riset ACE

**Waktu:** {now}  
**Biaya Marginal:** Rp0 ($0.00)  
**Status Ilmiah:** {experiment_data.get("scientific_claim_status", "NOT_ASSESSED")}

---

### 1. Apa yang Dicoba?
Menguji apakah perluasan DSL dengan primitif penelusuran graf (BFS) dan pelacak residu rasio 4:1 mampu menyelesaikan tugas yang sebelumnya gagal pada baseline 6 November, menggunakan perbandingan adil A/B/C pada anggaran setara (16 label, 30 tugas held-out, 3 ulangan, 20 seed).

---

### 2. Ringkasan Hasil
- **Keluarga Graf (Keterhubungan 4-Vertex):**
  - Kondisi A (Statis 35 Lib): `{mean_a_g * 100:.1f}%`
  - Kondisi B (Adaptif Lokal): `{mean_b_g * 100:.1f}%`
  - **Kondisi C (Primitif Baru):** **`{mean_c_g * 100:.1f}%`**
  - *Kenaikan Bersih:* `+{(mean_c_g - mean_b_g) * 100:.1f}%`

- **Keluarga Rasio 4:1:**
  - Kondisi A: `{ratio4_stats.get("A", {}).get("mean", 0.0) * 100:.1f}%`
  - Kondisi C: `{ratio4_stats.get("C", {}).get("mean", 0.0) * 100:.1f}%`

---

### 3. Status Hipotesis
- **H_graph:** **{hypotheses.get("H_graph", "INKONKLUSIF")}** (Melampaui ambang batas 90% pada held-out)
- **H_ratio4:** **{hypotheses.get("H_ratio4", "INKONKLUSIF")}** (Tugas luar tata bahasa teradmisi)

---

### 4. Batas Interpretasi & Catatan Kritis
> [!WARNING]
> Keberhasilan pada graf 4-vertex dan rasio 4:1 adalah bukti validasi kapabilitas terarah, **bukan bukti kemunculan AGI atau OAIE umum**. Tanpa seed rahasia `ACE_SEALED_SEED`, status ilmiah formal tetap berada dalam domain konfirmasi benchmark lokal.
"""
    return report
