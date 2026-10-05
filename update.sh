#!/usr/bin/env bash
# Refresh the 2026/27 forecast after a new matchday and publish it.
#   ./update.sh            # data -> forecast -> figures -> page/README -> commit & push
#   ./update.sh --no-push  # everything except the git push
set -euo pipefail
cd "$(dirname "$0")"
# activates ./.venv if present; with conda, activate your environment before running this
[ -f .venv/bin/activate ] && source .venv/bin/activate

python scripts/01_build_dataset.py
python scripts/03_forecast_2026_27.py
python scripts/04_figures.py
python scripts/05_report.py

if [ "${1:-}" != "--no-push" ]; then
  git add data results figures docs README.md
  git commit -m "Forecast update: $(cat data/LAST_UPDATE)" || echo "nothing to commit"
  git push
fi
