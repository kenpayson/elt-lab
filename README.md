# elt-lab: NYC 311 ELT Pipeline

An end-to-end ELT pipeline that pulls New York City 311 service requests from the public NYC Open Data API, loads them into DuckDB, transforms them with dbt, and visualizes the results in Tableau.

Built by [Ken Payson](https://www.linkedin.com/in/ken-payson/) as a hands-on portfolio project.

## Architecture

```
NYC Open Data API (311 requests)
        │  Python (extract + load)
        ▼
DuckDB (raw tables)
        │  dbt (staging → marts)
        ▼
DuckDB (analytics-ready models)
        │
        ▼
Tableau dashboards
```

## Tech stack

| Layer | Tool |
|---|---|
| Extract & load | Python (`requests`) |
| Warehouse | DuckDB |
| Transformation | dbt (`dbt-duckdb`) |
| Visualization | Tableau |
| Environment | Ubuntu on WSL |
| AI assistance | Claude Code (with every change reviewed by me) |

## Project structure

```
elt-lab/
├── extract/          # Python scripts that call the 311 API and load DuckDB
├── dbt/              # dbt project
│   ├── models/
│   │   ├── staging/  # cleaned, renamed source data
│   │   └── marts/    # analytics-ready models
│   └── dbt_project.yml
├── data/             # local DuckDB file (not committed)
└── README.md
```

## How to run

1. Clone the repo and create a Python virtual environment:
   ```bash
   git clone https://github.com/<your-username>/elt-lab.git
   cd elt-lab
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Extract and load the raw data:
   ```bash
   python extract/<your_extract_script>.py
   ```
3. Build the dbt models:
   ```bash
   cd dbt
   dbt build
   ```
4. Connect Tableau to the DuckDB file in `data/` and open the dashboards.

## What the models do

- **Staging:** standardizes column names, data types and timestamps from the raw 311 data.
- **Marts:** analytics-ready tables for request volume, complaint types, boroughs and resolution time.

## Data quality

Results are checked by confirming row counts and the grain of each model against the raw data.

## Next steps

- Extend the same pattern to extract data from a Salesforce developer org.
- Add more dbt tests and documentation.

## How I use AI on this project

I use Claude Code to speed up profiling the data, drafting models and writing documentation. I review every line before committing it and verify results against the data myself.
