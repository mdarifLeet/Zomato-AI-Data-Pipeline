import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

DBT_TARGET = os.getenv("DBT_TARGET", "duckdb")
DBT_BIN = "/opt/airflow/dbt_venv/bin/dbt"
DBT_FLAGS = f"--project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt --target {DBT_TARGET}"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "zomato_batch_pipeline",
    default_args=default_args,
    description="Zomato ELT Pipeline: Run dbt -> Data Quality Tests",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["zomato", "dbt", DBT_TARGET],
) as dag:

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{DBT_BIN} run {DBT_FLAGS}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT_BIN} test {DBT_FLAGS}",
    )

    dbt_run >> dbt_test
