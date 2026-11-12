import os
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization

load_dotenv()

RAW_TABLES = [
    "restaurants",
    "users",
    "food",
    "menu",
    "orders",
    "order_items",
    "reviews",
]

SEEDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "zomato", "seeds"))
os.makedirs(SEEDS_DIR, exist_ok=True)


def get_snowflake_connection():
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
            schema="RAW",
        )
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "ZOMATO"),
        schema="RAW",
    )


def main():
    conn = get_snowflake_connection()
    try:
        for table in RAW_TABLES:
            print(f"Exporting ZOMATO.RAW.{table.upper()}...")
            df = pd.read_sql(f"SELECT * FROM ZOMATO.RAW.{table.upper()}", conn)
            df.columns = [c.lower() for c in df.columns]
            out_path = os.path.join(SEEDS_DIR, f"{table}.csv")
            df.to_csv(out_path, index=False)
            print(f"  -> Saved {len(df)} rows to {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()