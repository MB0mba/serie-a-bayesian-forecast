"""Backtest: forecast Serie A 2025/26 at matchdays 0, 12, 19 and 28 and compare with the final table.

    python scripts/02_backtest_2025_26.py            (~20 min with 4 cores)

Writes results/2025-26/. Each cut-off is a full refit of the model on the five
previous seasons plus the matchdays already played.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from seriea import data, pipeline  # noqa: E402

df = data.load(ROOT / "data" / "seriea_2020_2027.csv")
pipeline.run(df, "2025/2026", [0, 12, 19, 28], ROOT / "results" / "2025-26")
