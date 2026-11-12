import duckdb, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "zomato", "seeds").replace("\\", "/")
DST = os.path.join(ROOT, "zomato", "seeds_sample").replace("\\", "/")
os.makedirs(DST, exist_ok=True)

N_ORDERS = 50000

con = duckdb.connect()
for t in ["restaurants", "users", "food", "menu", "orders", "order_items", "reviews"]:
    con.execute(
        f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('{SRC}/{t}.csv', all_varchar=true)"
    )

con.execute(f"CREATE TABLE s_orders AS SELECT * FROM orders USING SAMPLE {N_ORDERS} ROWS (reservoir, 42)")
con.execute("CREATE TABLE s_items AS SELECT * FROM order_items WHERE order_id IN (SELECT order_id FROM s_orders)")
con.execute("CREATE TABLE s_reviews AS SELECT * FROM reviews WHERE order_id IN (SELECT order_id FROM s_orders)")
con.execute("CREATE TABLE s_users AS SELECT * REPLACE ('' AS password) FROM users WHERE user_id IN (SELECT user_id FROM s_orders)")
con.execute("CREATE TABLE s_rest AS SELECT * FROM restaurants WHERE id IN (SELECT r_id FROM s_orders)")
con.execute("CREATE TABLE s_menu AS SELECT * FROM menu WHERE r_id IN (SELECT r_id FROM s_orders)")

for src, name in [("s_orders", "orders"), ("s_items", "order_items"), ("s_reviews", "reviews"),
                  ("s_users", "users"), ("s_rest", "restaurants"), ("s_menu", "menu"), ("food", "food")]:
    con.execute(f"COPY {src} TO '{DST}/{name}.csv' (HEADER, DELIMITER ',')")
    n = con.execute(f"SELECT COUNT(*) FROM {src}").fetchall()[0][0]
    print(name, n)