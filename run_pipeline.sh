#!/usr/bin/env bash
# ORCHESTRATION (the simple version): run every step in order, stop on first failure.
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate

echo "== 1. Extract + Load =="
python extract_load.py --days "${DAYS:-7}"

echo "== 2. Transform + Test (dbt) =="
cd dbt_project
dbt source freshness
dbt build            # runs models AND tests, in dependency order
cd ..

echo "== 3. Serve =="
python export_for_tableau.py

echo "Pipeline finished OK at $(date)"
