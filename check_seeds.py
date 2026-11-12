import duckdb, os

for t in ["restaurants", "users", "food", "menu", "orders", "order_items", "reviews"]:
    path = f"zomato/seeds/{t}.csv"
    if not os.path.exists(path):
        print(t, "-> FILE MISSING")
        continue
    try:
        n = duckdb.sql(f"SELECT COUNT(*) FROM read_csv_auto('{path}', all_varchar=true)").fetchall()[0][0]
        print(t, n)
    except Exception as e:
        print(t, "-> ERROR:", str(e)[:200])