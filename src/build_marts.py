"""Run sql/marts.sql in DuckDB and write each mart to data/marts/<name>.parquet.

Inputs: data/observed_daily.parquet (geo-day) and data/geo_assignment.csv.
Run after run_timeline.py; chapters 1-4 read the marts.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
MARTS = ["national_day", "national_week", "geo_test_pairs", "platform_claims", "period_revenue"]


def main():
    out = ROOT / "data" / "marts"
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW obs AS SELECT * FROM read_parquet('{(ROOT / 'data' / 'observed_daily.parquet').as_posix()}')")
    con.execute(f"CREATE VIEW asg AS SELECT * FROM read_csv_auto('{(ROOT / 'data' / 'geo_assignment.csv').as_posix()}')")
    con.execute((ROOT / "sql" / "marts.sql").read_text(encoding="utf-8"))
    for name in MARTS:
        path = (out / f"{name}.parquet").as_posix()
        con.execute(f"COPY {name} TO '{path}' (FORMAT PARQUET)")
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"{name:16s} {n:6d} rows")


def read(name: str):
    import pandas as pd
    return pd.read_parquet(ROOT / "data" / "marts" / f"{name}.parquet")


if __name__ == "__main__":
    main()
