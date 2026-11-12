import re
import streamlit as st
from google import genai
from db import DB_ENGINE, generate_with_retry, get_api_key, query_df

FORBIDDEN_WORDS = [
    "drop", "delete", "truncate", "alter", "update", "insert",
    "create", "replace", "grant", "revoke",
]

EXAMPLE_QUESTIONS = [
    "Top 10 cities by GMV",
    "Which cuisine has the most orders?",
    "Average delivery time by city, worst first",
    "Cancel rate by payment method",
]

FALLBACK_SQL = {
    "top 10 cities by gmv": """SELECT
    city,
    ROUND(SUM(gmv), 2) AS total_gmv,
    SUM(delivered_orders) AS delivered_orders
FROM mart_daily_city_revenue
GROUP BY city
ORDER BY total_gmv DESC
LIMIT 10""",
    "which cuisine has the most orders": """SELECT
    cuisine,
    COUNT(*) AS total_orders,
    ROUND(SUM(CASE WHEN is_delivered THEN sales_amount ELSE 0 END), 2) AS delivered_gmv
FROM fct_orders
GROUP BY cuisine
ORDER BY total_orders DESC
LIMIT 10""",
    "average delivery time by city, worst first": """SELECT
    city,
    ROUND(AVG(delivery_time_min), 2) AS avg_delivery_time_min,
    COUNT(*) AS delivered_orders
FROM fct_orders
WHERE is_delivered
GROUP BY city
ORDER BY avg_delivery_time_min DESC
LIMIT 15""",
    "cancel rate by payment method": """SELECT
    payment_method,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN order_status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
    ROUND(
        SUM(CASE WHEN order_status = 'Cancelled' THEN 1.0 ELSE 0.0 END) / NULLIF(COUNT(*), 0),
        4
    ) AS cancel_rate
FROM fct_orders
GROUP BY payment_method
ORDER BY cancel_rate DESC""",
}

client = genai.Client(api_key=get_api_key())

SCHEMA = """
Tables available in the MARTS schema. Use bare table names with no schema prefix:

1. dim_restaurants (restaurant_id, restaurant_name, city, rating, rating_count, cost_for_two, cuisine, license_no)
2. dim_customer (customer_id, customer_name, email, age, age_segment, gender, marital_status, occupation, income_band, education, family_size)
3. dim_food (f_id, food_name, veg_or_non_veg)
4. dim_date (date_day, year, month, month_name, day_name, is_weekend)
5. fct_orders (order_id, order_timestamp, order_date, customer_id, restaurant_id, city, cuisine, items_count, sales_qty, subtotal, discount, delivery_fee, gst, sales_amount, currency, payment_method, order_status, is_delivered, customer_rating, delivery_time_min)
6. fct_order_items (order_item_id, order_id, restaurant_id, f_id, price, quantity, line_amount, order_date, city, is_delivered)
7. mart_daily_city_revenue (order_date, city, orders, delivered_orders, cancel_rate, gmv, aov)
8. mart_delivery_sla (city, order_hour, delivered_orders, p50, p90)
9. mart_restaurant_performance (restaurant_id, restaurant_name, city, cuisine, orders, revenue, avg_customer_rating, avg_delivery_min)
"""

SYSTEM_PROMPT = f"""
You are an expert SQL data analyst generating queries for {DB_ENGINE.upper()}.
Convert natural language questions into executable ANSI SQL SELECT statements.

SCHEMA:
{SCHEMA}

RULES:
1. Return ONLY executable SQL inside a ```sql code block. No explanation outside the block.
2. SELECT queries only. Never use DROP, DELETE, TRUNCATE, UPDATE, INSERT, ALTER, CREATE, REPLACE.
3. Always use NULLIF(denominator, 0) when dividing and standard CASE WHEN instead of IFF.
"""


def fallback_sql_for_question(question: str) -> str:
    q = question.strip().lower().rstrip("?.!")
    if q in FALLBACK_SQL:
        return FALLBACK_SQL[q]
    if "gmv" in q and "cit" in q:
        return FALLBACK_SQL["top 10 cities by gmv"]
    if "cuisine" in q and "order" in q:
        return FALLBACK_SQL["which cuisine has the most orders"]
    if "delivery" in q and ("time" in q or "sla" in q or "worst" in q):
        return FALLBACK_SQL["average delivery time by city, worst first"]
    if "cancel" in q and "payment" in q:
        return FALLBACK_SQL["cancel rate by payment method"]
    if "restaurant" in q:
        return """SELECT
    restaurant_name,
    city,
    cuisine,
    orders,
    ROUND(revenue, 2) AS revenue,
    avg_customer_rating,
    avg_delivery_min
FROM mart_restaurant_performance
ORDER BY revenue DESC
LIMIT 10"""
    return FALLBACK_SQL["top 10 cities by gmv"]


def generate_sql(question: str) -> str:
    try:
        raw = generate_with_retry(
            client=client,
            contents=question,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
        )
        match = re.search(r"```sql\s*(.*?)\s*```", raw, re.DOTALL)
        return match.group(1).strip() if match else raw.strip()
    except Exception:
        return fallback_sql_for_question(question)


def validate_sql(sql: str) -> bool:
    sql_lower = sql.lower()
    return not any(re.search(rf"\b{word}\b", sql_lower) for word in FORBIDDEN_WORDS)


def main():
    st.set_page_config(page_title="Zomato Text to SQL", layout="wide")
    st.title(f"Zomato AI Analytics (Text to SQL — {DB_ENGINE.upper()})")

    st.subheader("Example Questions")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    if "sql_question" not in st.session_state:
        st.session_state["sql_question"] = ""
    for idx, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[idx].button(q):
            st.session_state["sql_question"] = q

    question = st.text_input(
        "Ask a question about the Zomato dataset:",
        key="sql_question",
    )

    if question:
        sql = generate_sql(question)
        st.subheader("Generated SQL")
        st.code(sql, language="sql")

        if not validate_sql(sql):
            st.error("Generated SQL contains unsafe statement keywords.")
            return

        st.subheader("Query Results")
        with st.spinner(f"Running query in {DB_ENGINE.upper()}..."):
            try:
                df = query_df(sql, default_schema="MARTS")
                st.dataframe(df)
            except Exception as e:
                st.error(f"Execution Error: {e}")


if __name__ == "__main__":
    main()
