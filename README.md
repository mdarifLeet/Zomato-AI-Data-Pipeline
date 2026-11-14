## 🚀 Live Demo

| App | What it does | Link |
|-----|--------------|------|
| Text-to-SQL Analytics | Ask questions in plain English and get the generated SQL plus results from DuckDB | [Open app](https://mdarif-zomato-ai-data-pipeline.streamlit.app) |
| Customer Review Search & Q&A | RAG app that retrieves relevant customer reviews using embeddings and answers questions about them | [Open app](https://mdarif-ragchat-zomato-ai-data-pipeline.streamlit.app/) |

> **Note on data:** The hosted demos run on a small sample (e.g. 100 customer reviews and a sample dataset in `seeds_sample`) because the full dataset is too large for GitHub and Streamlit's free tier. The full pipeline runs locally.

> Both apps run on Streamlit Community Cloud's free tier. If one shows a "Yes, get this app back up!" button, click it and wait about a minute.

**Try asking:**
- Text-to-SQL: *"Top 10 cities by GMV"*, *"Cancel rate by payment method"*
- Review Q&A: *"What do customers say about delivery speed?"*, *"How is the service in Bangalore?"*

An ELT pipeline for a synthetic food-delivery dataset (10M orders, 23M order items). Raw files are loaded into **Snowflake** through an internal stage, **dbt** builds tested staging and mart layers, **Airflow** orchestrates it in Docker, and **Gemini**-powered scripts add text-to-SQL and review search on top.

The same dbt project also runs on **DuckDB** and **PostgreSQL**, so anyone can run it locally at zero cost with a small sample dataset included in this repo.

<!-- TODO: add the Streamlit GIF here once recorded -->
![Text-to-SQL demo](docs/images/streamlit-demo.gif)

## Architecture

```
Raw CSV files (orders, order_items, users, restaurants, food, menu, reviews)
        |
        v
Snowflake internal stage  ->  RAW tables          (PUT + COPY INTO, Airflow task: reload_raw)
        |
        v
dbt staging (stg_*)  ->  dbt marts                (Airflow task: dbt_build_core)
        |
        v
dim_*, fct_*, mart_*  ->  AI scripts (Gemini)     (text-to-SQL, review embeddings, RAG chat)
```

Three warehouse layers: **RAW** (data exactly as loaded, every column text), **STAGING** (typed and cleaned views) and **MARTS** (dimensions, facts and reports).

## Tech stack

| Tool | Role |
| --- | --- |
| Snowflake | Cloud data warehouse (RAW, STAGING, MARTS schemas) |
| dbt (dbt-snowflake, dbt-duckdb, dbt-postgres) | Transformations, incremental models, data tests |
| Apache Airflow | Orchestration (DAG `zomato_batch`) |
| Docker Compose | Runs Airflow and Postgres locally |
| DuckDB | Free local warehouse for running the project without Snowflake |
| Python + Gemini | Text-to-SQL, review embeddings, RAG chat |
| Streamlit | UI for the AI apps |

## Data

The dataset is **synthetic**: names, emails and passwords are generated, and emails use reserved `example.org` / `example.com` domains. The full data is too large for GitHub, so the repo ships a consistent random sample.

| Table | Full dataset | Sample in `zomato/seeds_sample/` |
| --- | ---: | ---: |
| orders | 10,000,000 | 50,000 |
| order_items | 22,998,179 | 114,852 |
| reviews | 300,000 | 1,546 |
| users | 100,000 | 31,924 |
| restaurants | 148,541 | 37,801 |
| menu | 1,179,936 | 361,177 |
| food | 371,561 | 371,561 |

The sample keeps 50,000 random orders and only the rows that belong to them, so every foreign key still resolves. It is built by `ai/make_sample.py` with a fixed seed.

## Data models

- **Staging views:** `stg_orders`, `stg_order_items`, `stg_users`, `stg_restaurants`, `stg_menu`, `stg_food`, `stg_reviews`
- **Dimensions:** `dim_customer`, `dim_restaurants`, `dim_food`, `dim_date`
- **Facts:** `fct_orders`, `fct_order_items` (incremental, merge on key)
- **Reports:** `mart_daily_city_revenue`, `mart_delivery_sla` (p50 / p90 delivery time by city and hour), `mart_restaurant_performance`

<!-- TODO: add docs/images/dbt-lineage.png from `dbt docs generate && dbt docs serve` -->
![dbt lineage](docs/images/dbt-lineage.png)

## AI features (`ai/`)

- `text_to_sql.py` - ask a question in plain English, get SQL against the marts, with a SELECT-only guard before anything runs
- `enrich_reviews.py` - enriches review text using Gemini
- `rag_chat.py` - chat over customer reviews using stored embeddings
- `make_sample.py` / `export_snowflake_raw.py` - build the sample dataset and export the raw Snowflake tables

<!-- TODO: add docs/images/streamlit-text-to-sql.png -->
![Text-to-SQL app](docs/images/streamlit-text-to-sql.png)

## Run it locally (DuckDB, no accounts needed)

Requires Python 3.11 or 3.12.

```bash
pip install duckdb dbt-duckdb streamlit google-genai pandas python-dotenv

# 1. Load the sample CSVs into a local DuckDB file
python load_duckdb.py

# 2. Build staging and marts
cd zomato
dbt run --target duckdb
dbt test --target duckdb
cd ..

# 3. Launch the text-to-SQL app
cd ai
streamlit run text_to_sql.py
```

<!-- TODO: verify these steps from a fresh clone, then delete this comment.
     Also confirm: where profiles.yml comes from (add profiles.yml.example and say "copy it to profiles.yml"),
     that dbt-duckdb works with the DuckDB version you installed, and that ai/.env needs GEMINI_API_KEY and DB_ENGINE=duckdb. -->

`python load_duckdb.py --full` loads the complete exported CSVs (about 33M rows) into a separate `zomato_full.duckdb`. Those CSVs are git-ignored; export them from Snowflake with `ai/export_snowflake_raw.py`.

## Run the full pipeline (Airflow + Snowflake)

1. Install Docker Desktop.
2. Create a Snowflake key pair and register the public key on your Snowflake user.
3. Create `airflow/.env` (never commit this file):

   ```
   SNOWFLAKE_USER=
   SNOWFLAKE_ACCOUNT=
   SNOWFLAKE_PASSWORD=
   SNOWFLAKE_KEY_PASSPHRASE=
   AIRFLOW_ADMIN_PASSWORD=
   ```

4. Create `ai/.env` with `GEMINI_API_KEY=` and `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=`.
5. Create `zomato/profiles.yml` for your account (git-ignored). The private key is mounted into the Airflow containers at `/opt/airflow/.snowflake/rsa_key.p8`.
6. Start Airflow:

   ```bash
   cd airflow
   docker compose up -d
   ```

7. Open http://localhost:8080, log in as `admin`, and trigger the `zomato_batch` DAG.

<!-- TODO: add docs/images/airflow-dag.png -->
![Airflow DAG](docs/images/airflow-dag.png)

## Proof it ran on Snowflake

The pipeline was built and run on a Snowflake trial account. The setup scripts are in [`snowflake/`](snowflake/) (warehouse and roles, stage and file formats, raw tables, `COPY INTO`).

<!-- TODO: save the five worksheets into snowflake/ with secrets removed, then keep the link above -->

| | |
| --- | --- |
| ![Query activity by type](docs/images/snowflake-query-types.png) | ![RAW tables and stage](docs/images/snowflake-raw-tables.png) |
| Statement types over 30 days: PUT and COPY INTO for loading, views, MERGE and grants. | Seven RAW tables and one internal stage in the `ZOMATO` database. |

![Warehouse](docs/images/snowflake-warehouse.png)

The trial has ended or will end, so Snowflake is no longer needed to run the project. Use the DuckDB path above.

## Design decisions

- **Raw layer is all text.** Snowflake `RAW` tables load every column as `VARCHAR`. Typing happens in the staging views, using safe casts, so a bad value cannot fail the load.
- **Separate STAGING and MARTS schemas.** A custom `generate_schema_name` macro puts models in plain `STAGING` and `MARTS` schemas instead of dbt's default `<target schema>_<custom schema>` names.
- **Portable SQL.** <!-- confirm these macros exist in zomato/macros/cross_db_utils.sql --> Cross-database macros (`try_int`, `try_decimal`, `regex_extract`) and Jinja branches on `target.type` replace Snowflake-only functions, so the same models run on Snowflake, DuckDB and PostgreSQL.
- **Large tables are not loaded with `dbt seed`.** Seeds are parsed in Python and are meant for small lookup files, so the 33M-row tables are loaded directly (`COPY INTO` on Snowflake, DuckDB's CSV reader locally). Only the small sample is committed.
- **Incremental facts.** `fct_orders` and `fct_order_items` use incremental models with merge, so reruns do not rebuild 33M rows.
- **Safe text-to-SQL.** Generated SQL is checked against a forbidden-keyword list and runs read-only against the marts.

## Limitations

- The data is synthetic, so the analysis findings say nothing about real restaurants.
- The DuckDB path uses a 50,000-order sample. Full-size behavior was tested on Snowflake only.
- Text-to-SQL can still produce wrong queries. The guard stops destructive statements, not incorrect ones.
- DuckDB allows a single writer, so close the Streamlit app before running dbt.

## Project structure

```
airflow/          Airflow DAG, Dockerfile, docker-compose.yaml
zomato/           dbt project (models, macros, tests, seeds_sample)
  models/staging  stg_* views that clean the raw tables
  models/marts    dimensions, facts and reports
ai/               Gemini-powered scripts and sample/export helpers
snowflake/        Snowflake setup and load scripts
docs/images/      Screenshots used in this README
load_duckdb.py    Loads CSVs into a local DuckDB file
```

## Notes

- Secrets (`.env`, key files, `profiles.yml`) and large data files (`zomato/seeds/*.csv`, `*.duckdb`) are excluded through `.gitignore`.

## Author

Md Arif - <!-- add your LinkedIn / email -->
