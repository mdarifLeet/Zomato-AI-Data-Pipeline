import os
import shutil
import threading
import time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

AI_DIR = Path(__file__).resolve().parent
REPO_ROOT = AI_DIR.parent
load_dotenv(AI_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

DB_ENGINE = os.getenv("DB_ENGINE", "duckdb").lower()
DEFAULT_DUCKDB_PATH = REPO_ROOT / "zomato" / "zomato.duckdb"
_INIT_LOCK = threading.Lock()
_DB_READY = False

CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.8-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-pro",
]

BOOTSTRAP_SQL = [
    "CREATE SCHEMA IF NOT EXISTS RAW",
    "CREATE SCHEMA IF NOT EXISTS STAGING",
    "CREATE SCHEMA IF NOT EXISTS MARTS",
    """CREATE OR REPLACE VIEW STAGING.stg_food AS
    SELECT
        f_id,
        item AS food_name,
        CASE
            WHEN LOWER(CAST(veg_or_non_veg AS VARCHAR)) = 'veg' THEN 'Veg'
            WHEN LOWER(CAST(veg_or_non_veg AS VARCHAR)) = 'non-veg' THEN 'Non-veg'
            ELSE CAST(veg_or_non_veg AS VARCHAR)
        END AS veg_or_non_veg
    FROM RAW.food
    WHERE f_id IS NOT NULL""",
    """CREATE OR REPLACE VIEW STAGING.stg_menu AS
    SELECT
        menu_id,
        TRY_CAST(r_id AS BIGINT) AS restaurant_id,
        f_id,
        cuisine,
        TRY_CAST(price AS DECIMAL(10, 2)) AS price
    FROM RAW.menu
    WHERE TRY_CAST(r_id AS BIGINT) IS NOT NULL
      AND TRY_CAST(price AS DECIMAL(10, 2)) > 0""",
    """CREATE OR REPLACE VIEW STAGING.stg_restaurants AS
    SELECT
        TRY_CAST(id AS BIGINT) AS restaurant_id,
        name AS restaurant_name,
        TRIM(REGEXP_REPLACE(COALESCE(NULLIF(regexp_extract(CAST(city AS VARCHAR), '[^,]+$'), ''), CAST(city AS VARCHAR)), '-[0-9]+$', '')) AS city,
        TRY_CAST(NULLIF(CAST(rating AS VARCHAR), '--') AS DECIMAL(3, 1)) AS rating,
        TRY_CAST(NULLIF(regexp_extract(REPLACE(CAST(rating_count AS VARCHAR), ',', ''), '[0-9]+'), '') AS BIGINT) AS rating_count,
        TRY_CAST(NULLIF(regexp_extract(REPLACE(CAST(cost AS VARCHAR), ',', ''), '[0-9]+'), '') AS BIGINT) AS cost_for_two,
        cuisine,
        NULLIF(regexp_extract(CAST(lic_no AS VARCHAR), '[0-9]+'), '') AS license_no
    FROM RAW.restaurants
    WHERE TRY_CAST(id AS BIGINT) IS NOT NULL""",
    """CREATE OR REPLACE VIEW STAGING.stg_users AS
    SELECT
        TRY_CAST(user_id AS BIGINT) AS customer_id,
        name AS customer_name,
        LOWER(TRIM(CAST(email AS VARCHAR))) AS email,
        TRY_CAST(age AS BIGINT) AS age,
        gender,
        marital_status,
        occupation,
        monthly_income AS income_band,
        education,
        TRY_CAST(family_size AS BIGINT) AS family_size
    FROM RAW.users
    WHERE TRY_CAST(user_id AS BIGINT) IS NOT NULL""",
    """CREATE OR REPLACE VIEW STAGING.stg_orders AS
    SELECT
        order_id,
        CAST(order_timestamp AS TIMESTAMP) AS order_timestamp,
        CAST(order_date AS DATE) AS order_date,
        TRY_CAST(user_id AS BIGINT) AS customer_id,
        TRY_CAST(r_id AS BIGINT) AS restaurant_id,
        TRIM(COALESCE(NULLIF(regexp_extract(CAST(restaurant_city AS VARCHAR), '[^,]+$'), ''), CAST(restaurant_city AS VARCHAR))) AS city,
        cuisine,
        TRY_CAST(items_count AS BIGINT) AS items_count,
        TRY_CAST(sales_qty AS BIGINT) AS sales_qty,
        TRY_CAST(subtotal AS DECIMAL(10, 2)) AS subtotal,
        TRY_CAST(discount AS DECIMAL(10, 2)) AS discount,
        TRY_CAST(delivery_fee AS DECIMAL(10, 2)) AS delivery_fee,
        TRY_CAST(gst AS DECIMAL(10, 2)) AS gst,
        TRY_CAST(sales_amount AS DECIMAL(10, 2)) AS sales_amount,
        currency,
        payment_method,
        order_status,
        (order_status = 'Delivered') AS is_delivered,
        TRY_CAST(customer_rating AS DECIMAL(3, 1)) AS customer_rating,
        TRY_CAST(delivery_time_min AS DECIMAL(10, 2)) AS delivery_time_min
    FROM RAW.orders""",
    """CREATE OR REPLACE VIEW STAGING.stg_order_items AS
    SELECT
        order_item_id,
        order_id,
        TRY_CAST(r_id AS BIGINT) AS restaurant_id,
        f_id,
        CAST(price AS DECIMAL(10, 2)) AS price,
        CAST(quantity AS BIGINT) AS quantity,
        CAST(line_amount AS DECIMAL(10, 2)) AS line_amount
    FROM RAW.order_items""",
    """CREATE OR REPLACE VIEW STAGING.stg_reviews AS
    SELECT
        r.review_id,
        r.order_id,
        TRY_CAST(r.user_id AS BIGINT) AS customer_id,
        CAST(r.restaurant_id AS VARCHAR) AS restaurant_id,
        TRY_CAST(r.rating AS BIGINT) AS rating,
        CAST(r.comment AS VARCHAR) AS comment,
        CAST(r.review_date AS DATE) AS review_date,
        res.city AS city
    FROM RAW.reviews r
    LEFT JOIN STAGING.stg_restaurants res
        ON TRY_CAST(r.restaurant_id AS BIGINT) = res.restaurant_id
    WHERE r.comment IS NOT NULL""",
    """CREATE OR REPLACE VIEW MARTS.dim_food AS
    SELECT f_id, food_name, veg_or_non_veg FROM STAGING.stg_food""",
    """CREATE OR REPLACE VIEW MARTS.dim_restaurants AS
    SELECT restaurant_id, restaurant_name, city, rating, rating_count, cost_for_two, cuisine, license_no
    FROM STAGING.stg_restaurants""",
    """CREATE OR REPLACE VIEW MARTS.dim_customer AS
    SELECT
        customer_id,
        customer_name,
        email,
        age,
        CASE
            WHEN age < 25 THEN 'Under 25'
            WHEN age BETWEEN 25 AND 34 THEN '25-34'
            WHEN age BETWEEN 35 AND 44 THEN '35-44'
            WHEN age >= 45 THEN '45+'
            ELSE 'Unknown'
        END AS age_segment,
        gender,
        marital_status,
        occupation,
        income_band,
        education,
        family_size
    FROM STAGING.stg_users""",
    """CREATE OR REPLACE VIEW MARTS.dim_date AS
    WITH spine AS (
        SELECT CAST(gs AS DATE) AS date_day
        FROM generate_series(CAST('2024-01-01' AS DATE), CAST('2026-12-31' AS DATE), INTERVAL '1 day') AS t(gs)
    )
    SELECT
        date_day,
        EXTRACT(YEAR FROM date_day) AS year,
        EXTRACT(MONTH FROM date_day) AS month,
        STRFTIME(date_day, '%b') AS month_name,
        STRFTIME(date_day, '%a') AS day_name,
        (ISODOW(date_day) >= 6) AS is_weekend
    FROM spine""",
    """CREATE OR REPLACE TABLE MARTS.fct_orders AS
    SELECT * FROM STAGING.stg_orders""",
    """CREATE OR REPLACE TABLE MARTS.fct_order_items AS
    SELECT
        oi.order_item_id,
        oi.order_id,
        oi.restaurant_id,
        oi.f_id,
        oi.price,
        oi.quantity,
        oi.line_amount,
        COALESCE(o.order_date, CAST('1900-01-01' AS DATE)) AS order_date,
        o.city,
        o.is_delivered
    FROM STAGING.stg_order_items oi
    LEFT JOIN STAGING.stg_orders o ON oi.order_id = o.order_id""",
    """CREATE OR REPLACE VIEW MARTS.mart_daily_city_revenue AS
    SELECT
        order_date,
        city,
        COUNT(*) AS orders,
        SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered_orders,
        ROUND(COALESCE(SUM(CASE WHEN order_status = 'Cancelled' THEN 1.0 ELSE 0.0 END) / NULLIF(COUNT(*), 0), 0), 4) AS cancel_rate,
        SUM(CASE WHEN is_delivered THEN sales_amount ELSE 0 END) AS gmv,
        ROUND(COALESCE(SUM(CASE WHEN is_delivered THEN sales_amount ELSE 0.0 END) / NULLIF(SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END), 0), 0), 2) AS aov
    FROM MARTS.fct_orders
    GROUP BY 1, 2""",
    """CREATE OR REPLACE VIEW MARTS.mart_delivery_sla AS
    SELECT
        city,
        EXTRACT(HOUR FROM CAST(order_timestamp AS TIMESTAMP)) AS order_hour,
        SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered_orders,
        ROUND(CAST(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_time_min) AS DECIMAL(10, 2)), 1) AS p50,
        ROUND(CAST(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delivery_time_min) AS DECIMAL(10, 2)), 1) AS p90
    FROM MARTS.fct_orders
    WHERE is_delivered
    GROUP BY 1, 2""",
    """CREATE OR REPLACE VIEW MARTS.mart_restaurant_performance AS
    SELECT
        f.restaurant_id,
        r.restaurant_name,
        r.city,
        r.cuisine,
        COUNT(*) AS orders,
        SUM(CASE WHEN f.is_delivered THEN f.sales_amount ELSE 0 END) AS revenue,
        ROUND(CAST(AVG(f.customer_rating) AS DECIMAL(10, 2)), 2) AS avg_customer_rating,
        ROUND(CAST(AVG(f.delivery_time_min) AS DECIMAL(10, 2)), 1) AS avg_delivery_min
    FROM MARTS.fct_orders f
    LEFT JOIN MARTS.dim_restaurants r ON f.restaurant_id = r.restaurant_id
    GROUP BY 1, 2, 3, 4""",
]


def ensure_duckdb_initialized(db_path: str) -> None:
    global _DB_READY
    if _DB_READY:
        return

    with _INIT_LOCK:
        if _DB_READY:
            return

        import duckdb

        path_obj = Path(db_path)
        if path_obj.exists():
            try:
                check_conn = duckdb.connect(str(path_obj), read_only=True)
                try:
                    tables = check_conn.execute(
                        "SELECT count(*) FROM information_schema.tables WHERE LOWER(table_schema) = 'marts'"
                    ).fetchone()[0]
                finally:
                    check_conn.close()
                if tables >= 5:
                    _DB_READY = True
                    return
            except Exception:
                pass

        # Build atomically in a temporary file first so concurrent threads never collide
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path_obj.parent / f"build_{os.getpid()}.duckdb"
        if tmp_path.exists():
            tmp_path.unlink()

        seeds_dir = REPO_ROOT / "zomato" / "seeds_sample"
        raw_tables = ["restaurants", "users", "food", "menu", "orders", "order_items", "reviews"]

        conn = duckdb.connect(str(tmp_path), read_only=False)
        try:
            conn.execute("CREATE SCHEMA IF NOT EXISTS RAW")
            for t in raw_tables:
                csv_file = (seeds_dir / f"{t}.csv").as_posix()
                conn.execute(
                    f"CREATE OR REPLACE TABLE RAW.{t} AS SELECT * FROM read_csv_auto('{csv_file}', all_varchar=true)"
                )
            for stmt in BOOTSTRAP_SQL:
                conn.execute(stmt)
        finally:
            conn.close()

        if path_obj.exists():
            try:
                path_obj.unlink()
            except Exception:
                pass
        shutil.move(str(tmp_path), str(path_obj))
        _DB_READY = True


def get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return ""


def get_model_name() -> str:
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if model == "gemini-2.5-flash":
        return "gemini-3.8-flash"
    return model


def generate_with_retry(
    client: genai.Client,
    contents: str,
    system_instruction: str = None,
    temperature: float = 0.0,
    response_mime_type: str = None,
) -> str:
    preferred = get_model_name()
    models_to_try = [preferred] + [m for m in CANDIDATE_MODELS if m != preferred]

    cfg_kwargs = {"temperature": temperature}
    if system_instruction:
        cfg_kwargs["system_instruction"] = system_instruction
    if response_mime_type:
        cfg_kwargs["response_mime_type"] = response_mime_type
    config = types.GenerateContentConfig(**cfg_kwargs)

    last_err = None
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                return resp.text
            except Exception as e:
                last_err = e
                err_str = str(e)
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
    raise last_err


def get_connection(default_schema: str = "MARTS", read_only: bool = True):
    if DB_ENGINE == "duckdb":
        import duckdb
        db_path = os.getenv("DUCKDB_PATH", str(DEFAULT_DUCKDB_PATH))
        ensure_duckdb_initialized(db_path)
        conn = duckdb.connect(db_path, read_only=read_only)
        conn.execute(f"SET search_path = '{default_schema},STAGING,RAW,main'")
        return conn

    if DB_ENGINE == "postgres":
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "airflow"),
            password=os.getenv("POSTGRES_PASSWORD", "airflow"),
            dbname=os.getenv("POSTGRES_DB", "airflow"),
            options=f"-c search_path={default_schema},STAGING,RAW,public",
        )

    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    if key_path and os.path.exists(key_path):
        with open(key_path, "rb") as key_file:
            passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
            p_key = serialization.load_pem_private_key(
                key_file.read(),
                password=passphrase.encode() if passphrase else None,
            )
        pk_bytes = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            private_key=pk_bytes,
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            database=os.getenv("SNOWFLAKE_DATABASE", "ZOMATO"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", default_schema),
        )
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "ZOMATO"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", default_schema),
    )


def query_df(sql: str, default_schema: str = "MARTS") -> pd.DataFrame:
    conn = get_connection(default_schema=default_schema, read_only=True)
    try:
        if DB_ENGINE == "duckdb":
            df = conn.execute(sql).df()
        else:
            df = pd.read_sql(sql, conn)
        df.columns = [c.upper() for c in df.columns]
        return df
    finally:
        conn.close()
