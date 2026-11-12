FROM apache/airflow:3.0.3

RUN pip install --no-cache-dir \
    apache-airflow-providers-snowflake \
    apache-airflow-providers-fab \
    duckdb \
    openai

RUN python -m venv /opt/airflow/dbt_venv && \
    /opt/airflow/dbt_venv/bin/pip install --no-cache-dir \
    "dbt-core" \
    "dbt-duckdb" \
    "dbt-postgres" \
    "dbt-snowflake"
