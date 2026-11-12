import duckdb, os, sys

ROOT = os.path.abspath(os.path.dirname(__file__))
use_full = "--full" in sys.argv

seeds = os.path.join(ROOT, "zomato", "seeds" if use_full else "seeds_sample").replace("\\", "/")
db_path = os.path.join(ROOT, "zomato", "zomato_full.duckdb" if use_full else "zomato.duckdb")

TABLES = ["restaurants", "users", "food", "menu", "orders", "order_items", "reviews"]

con = duckdb.connect(db_path)
con.execute("CREATE SCHEMA IF NOT EXISTS RAW")
for t in TABLES:
    con.execute(
        f"CREATE OR REPLACE TABLE RAW.{t} AS "
        f"SELECT * FROM read_csv_auto('{seeds}/{t}.csv', all_varchar=true)"
    )
    n = con.execute(f"SELECT COUNT(*) FROM RAW.{t}").fetchall()[0][0]
    print(t, n)
con.close()
print("Database written to", db_path)