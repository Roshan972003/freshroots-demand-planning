#!/bin/bash
# Weekly (or twice-weekly) run: refresh data/ from the SAP + inventory exports, then rebuild outputs.
# Usage: ./run_weekly.sh [YYYY-MM]   (optional planning-month override)
# Schedule (Mon & Thu, 7:30am):  30 7 * * 1,4 /path/to/demand-planning/run_weekly.sh >> out/run.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"

for f in weekly_sales sku_master distributor_master current_inventory calendar; do
  [ -s "data/$f.csv" ] || { echo "Missing or empty data/$f.csv" >&2; exit 1; }
done

stamp=$(date +%Y-%m-%d)
mkdir -p out/archive
python3 engine.py ${1:+--month "$1"} --out out
python3 build_dashboard.py ${1:-}
cp out/recommendations.csv "out/archive/recommendations_$stamp.csv"
echo "[$stamp] done: $(grep -c REORDER_NOW out/recommendations.csv) reorder-now, $(grep -c ',REVIEW,' out/recommendations.csv) for review"
