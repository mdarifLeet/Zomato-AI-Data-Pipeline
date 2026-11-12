import os
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

CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


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
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    if model == "gemini-2.5-flash":
        return "gemini-3.5-flash"
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
                # If model not found (404), immediately try next model in list
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break
                # If overloaded (503) or rate-limited (429), wait briefly and retry/fallback
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
    raise last_err


def get_connection(default_schema: str = "MARTS", read_only: bool = True):
    if DB_ENGINE == "duckdb":
        import duckdb
        db_path = os.getenv("DUCKDB_PATH", str(DEFAULT_DUCKDB_PATH))
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
