r"""
SERVE: export the dbt marts to CSV so Tableau (on Windows) can open them.
Files land in ./exports/. In Tableau: Connect > Text file, and paste
  \\wsl.localhost\Ubuntu\home\<you>\projects\elt-lab\exports
into the file dialog's address bar.
"""
from pathlib import Path
import duckdb

PROJECT_DIR = Path(__file__).resolve().parent
OUT = PROJECT_DIR / "exports"
OUT.mkdir(exist_ok=True)

con = duckdb.connect(str(PROJECT_DIR / "warehouse.duckdb"), read_only=True)
marts = con.execute("""
    select table_schema, table_name
    from information_schema.tables
    where table_schema like '%marts'
""").fetchall()

for schema, table in marts:
    path = OUT / f"{table}.csv"
    con.execute(f"COPY {schema}.{table} TO '{path}' (HEADER, DELIMITER ',')")
    n = con.execute(f"select count(*) from {schema}.{table}").fetchone()[0]
    print(f"  {schema}.{table} -> exports/{table}.csv ({n} rows)")
con.close()
