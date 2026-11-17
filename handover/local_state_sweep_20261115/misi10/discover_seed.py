"""Lanjutan Misi 10 — discovery satu seed pengganti (20261804).

Memakai discover() yang sama dari discover_bands.py (pola probe R5),
untuk SATU seed saja. Dipanggil: python3 discover_seed.py 20261804
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover_bands

if __name__ == "__main__":
    seed = int(sys.argv[1])
    rec = discover_bands.discover(seed)
    print(f"[m10-seed] band {seed}: DONE {rec['seconds']}s keys={rec['n_keys']} "
          f"chains={rec['n_chains']} digest={rec['catalog_digest']}", flush=True)
