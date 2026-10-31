# Zomato AI Data Pipeline

An ELT pipeline for food-delivery data. Airflow loads raw files into Snowflake, dbt transforms them into staging and mart layers (with tests), and Python scripts using Gemini add AI features on top. Everything runs in Docker.

## Architecture

```
Raw CSV files (orders, users, restaurants, food, menu, order items, reviews)
        |
        v
Snowflake stage  ->  RAW tables           (Airflow task: reload_raw, COPY INTO)
        |
        v
dbt staging (stg_*)  ->  dbt marts        (Airflow task: dbt_build_core, dbt build)
        |
        v
dim_*, fct_*, mart_*  ->  AI scripts (Gemini)
```

## Tech stack

| Tool | Role |
|---|---|
| Snowflake | Cloud data warehouse (RAW, STAGING, MARTS schemas) |
| dbt (dbt-snowflake) | Transformations, incremental models, data tests |
| Apache Airflow | Orchestration (DAG `zomato_batch`) |
| Docker Compose | Runs Airflow and Postgres locally |
| Python + Gemini | Text-to-SQL, review embeddings, RAG chat |

## Project structure

```
airflow/          Airflow DAG, Dockerfile, docker-compose.yaml
zomato/           dbt project (models, macros, tests)
  models/staging  stg_* views that clean the raw tables
  models/marts    dimensions, facts and reports
ai/               Gemini-powered scripts
```

## Data models

- **Dimensions:** `dim_customer`, `dim_restaurants`, `dim_food`, `dim_date`
- **Facts:** `fct_orders`, `fct_order_items` (incremental, merge on key)
- **Reports:** `mart_daily_city_revenue`, `mart_delivery_sla` (p50/p90 delivery time by city and hour), `mart_restaurant_performance`

## AI features (`ai/`)

- `enrich_reviews.py` - enriches review data using Gemini
- `review_embeddings.parquet` - stored review embeddings
- `rag_chat.py` - chat over the reviews
- `text_to_sql.py` - ask questions in plain English, get SQL against the marts

## How to run

1. Install Docker Desktop.
2. Create a Snowflake key pair and register the public key on your Snowflake user.
3. Create `airflow/.env` with these variables (values are yours, never commit this file):

```
SNOWFLAKE_USER=
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_KEY_PASSPHRASE=
AIRFLOW_ADMIN_PASSWORD=
```

4. Create `ai/.env` with:

```
GEMINI_API_KEY=
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=
```

5. Create `zomato/profiles.yml` for your Snowflake account (it is git-ignored). The private key is mounted into the Airflow containers at `/opt/airflow/.snowflake/rsa_key.p8`.
6. Start Airflow:

```
cd airflow
docker compose up -d
```

7. Open http://localhost:8080, log in as `admin`, and trigger the `zomato_batch` DAG.

## Notes

- Secrets (`.env`, key files, `profiles.yml`) are excluded through `.gitignore`.
- Models are placed in separate `STAGING` and `MARTS` schemas using a custom `generate_schema_name` macro.
