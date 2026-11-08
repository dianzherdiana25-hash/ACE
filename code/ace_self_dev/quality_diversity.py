"""Quality Diversity (QD) Archive for Autonomous Capability Evolution.

Implements MAP-Elites (Multi-dimensional Archive of Phenotypic Elites) inspired by
pyribs and modern open-ended search literature:
1. Replaces myopic scalar fitness selection with a multi-dimensional behavior grid.
2. Characterizes candidates across two orthogonal dimensions:
   - Dimension 1: Structural Representation Tier (Linear, Composite, Gated, Relational, Dispatch)
   - Dimension 2: Behavioral Output Density (Sparse, Balanced, Dense prediction profiles)
3. Preserves elite candidates in distinct behavioral niches, ensuring continuous structural
   diversity and preventing search collapse into narrow local optima.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import CodeCandidate


@dataclass(frozen=True)
class EliteEntry:
    """An elite candidate occupying a specific behavioral niche."""
    niche_key: Tuple[int, int]  # (complexity_tier, density_bin)
    candidate: CodeCandidate
    fitness: float             # Validation accuracy [0.0, 1.0]
    behavior_density: float    # Empirical positive prediction ratio
    novelty_score: float       # Behavioral separation metric
    generation_cycle: int


class QualityDiversityArchive:
    """2D MAP-Elites Grid Archive for behavioral novelty and candidate selection."""

    # Complexity tiers: 0=Linear, 1=Composite, 2=Gated, 3=Relational, 4=Dispatch
    COMPLEXITY_TIERS = 5
    # Density bins: 0=Sparse (<0.35), 1=Balanced (0.35..0.65), 2=Dense (>0.65)
    DENSITY_BINS = 3

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._grid: Dict[Tuple[int, int], EliteEntry] = {}
        self._total_insertions: int = 0
        if self.storage_path and self.storage_path.exists():
            self._load()

    @property
    def total_niches(self) -> int:
        return self.COMPLEXITY_TIERS * self.DENSITY_BINS

    @property
    def filled_niches(self) -> int:
        return len(self._grid)

    @property
    def coverage(self) -> float:
        return round(self.filled_niches / max(1, self.total_niches), 4)

    @property
    def max_fitness(self) -> float:
        if not self._grid:
            return 0.0
        return max(e.fitness for e in self._grid.values())

    def characterize_candidate(
        self,
        candidate: CodeCandidate,
        validation_predictions: List[bool],
    ) -> Tuple[int, int, float]:
        """Compute the behavioral coordinate (complexity_tier, density_bin, density_ratio)."""
        gene_dict = candidate.gene_dict or {}
        
        # Determine complexity tier
        if gene_dict.get("is_dispatch"):
            c_tier = 4
        elif gene_dict.get("is_relational") or gene_dict.get("is_relational_gated"):
            c_tier = 3
        elif gene_dict.get("is_gated"):
            c_tier = 2
        elif gene_dict.get("is_composite"):
            c_tier = 1
        else:
            c_tier = 0

        # Determine density ratio & bin
        if not validation_predictions:
            density_ratio = 0.5
        else:
            density_ratio = sum(1 for p in validation_predictions if p) / len(validation_predictions)

        if density_ratio < 0.35:
            d_bin = 0  # Sparse
        elif density_ratio <= 0.65:
            d_bin = 1  # Balanced
        else:
            d_bin = 2  # Dense

        return c_tier, d_bin, round(density_ratio, 4)

    def consider_candidate(
        self,
        candidate: CodeCandidate,
        fitness: float,
        validation_predictions: List[bool],
        cycle_id: int = 0,
    ) -> Tuple[bool, str]:
        """Evaluate candidate for inclusion in the MAP-Elites grid.
        
        Returns:
            (inserted, reason)
        """
        c_tier, d_bin, density_ratio = self.characterize_candidate(candidate, validation_predictions)
        niche = (c_tier, d_bin)

        # Compute novelty as distance to other elites' densities
        if not self._grid:
            novelty = 1.0
        else:
            dists = [abs(density_ratio - e.behavior_density) for e in self._grid.values()]
            novelty = round(sum(dists) / len(dists), 4)

        if niche not in self._grid:
            # Novel niche discovery!
            self._grid[niche] = EliteEntry(
                niche_key=niche,
                candidate=candidate,
                fitness=fitness,
                behavior_density=density_ratio,
                novelty_score=novelty,
                generation_cycle=cycle_id,
            )
            self._total_insertions += 1
            self._save()
            return True, f"Discovered novel niche {niche} (tier={c_tier}, density={density_ratio:.2f})"

        current_elite = self._grid[niche]
        # Superior fitness in the same niche
        if fitness > current_elite.fitness + 1e-6:
            self._grid[niche] = EliteEntry(
                niche_key=niche,
                candidate=candidate,
                fitness=fitness,
                behavior_density=density_ratio,
                novelty_score=novelty,
                generation_cycle=cycle_id,
            )
            self._total_insertions += 1
            self._save()
            return True, f"Outperformed elite in niche {niche} ({fitness:.4f} > {current_elite.fitness:.4f})"

        # Equal fitness but higher novelty
        if abs(fitness - current_elite.fitness) <= 1e-6 and novelty > current_elite.novelty_score + 0.05:
            self._grid[niche] = EliteEntry(
                niche_key=niche,
                candidate=candidate,
                fitness=fitness,
                behavior_density=density_ratio,
                novelty_score=novelty,
                generation_cycle=cycle_id,
            )
            self._total_insertions += 1
            self._save()
            return True, f"Higher novelty in niche {niche} ({novelty:.4f} > {current_elite.novelty_score:.4f})"

        return False, f"Did not surpass elite in niche {niche} (fit={fitness:.4f} vs {current_elite.fitness:.4f})"

    def sample_parent(self, mode: str = "balanced") -> Optional[CodeCandidate]:
        """Sample an elite candidate from the grid.
        
        Modes:
        - 'best': Returns elite with highest validation fitness.
        - 'diverse': Uniformly samples across filled niches to prevent converging to one basin.
        - 'novel': Returns the elite with the highest novelty score.
        """
        if not self._grid:
            return None

        if mode == "best":
            best_entry = max(self._grid.values(), key=lambda e: e.fitness)
            return best_entry.candidate
        elif mode == "novel":
            novel_entry = max(self._grid.values(), key=lambda e: e.novelty_score)
            return novel_entry.candidate
        else:
            # Balanced: rank by combination of fitness (0.7) and novelty (0.3)
            scored = [
                (e.fitness * 0.7 + e.novelty_score * 0.3, e.candidate)
                for e in self._grid.values()
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return scored[0][1]

    def get_all_elites(self) -> List[EliteEntry]:
        return list(self._grid.values())

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "total_niches": self.total_niches,
            "filled_niches": self.filled_niches,
            "coverage_pct": round(self.coverage * 100, 2),
            "max_fitness": self.max_fitness,
            "total_insertions": self._total_insertions,
            "elites": [
                {
                    "niche": list(e.niche_key),
                    "candidate_id": e.candidate.candidate_id,
                    "fitness": e.fitness,
                    "density": e.behavior_density,
                    "novelty": e.novelty_score,
                }
                for e in self._grid.values()
            ],
        }

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            f"{k[0]}_{k[1]}": {
                "niche_key": list(e.niche_key),
                "candidate": e.candidate.to_dict(),
                "fitness": e.fitness,
                "behavior_density": e.behavior_density,
                "novelty_score": e.novelty_score,
                "generation_cycle": e.generation_cycle,
            }
            for k, e in self._grid.items()
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text())
            for key_str, item in raw.items():
                c_tier, d_bin = item["niche_key"]
                cand = CodeCandidate.from_dict(item["candidate"])
                self._grid[(c_tier, d_bin)] = EliteEntry(
                    niche_key=(c_tier, d_bin),
                    candidate=cand,
                    fitness=item["fitness"],
                    behavior_density=item["behavior_density"],
                    novelty_score=item["novelty_score"],
                    generation_cycle=item["generation_cycle"],
                )
        except Exception:
            self._grid = {}
