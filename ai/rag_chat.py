import os
import time
import numpy as np
import pandas as pd
import streamlit as st
import snowflake.connector
from google import genai
from google.genai import types
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
CHAT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
NEW_REVIEWS = 100
TOP_K = 5
BATCH_SIZE = 50
CACHE_FILE = "review_embeddings.parquet"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_connection():
    with open(os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"), "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE").encode(),
        )
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=pkb,
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


def read_reviews_from_snowflake():
    conn = get_connection()
    try:
        query = f"""
            SELECT REVIEW_ID, CITY, RATING, COMMENT
            FROM ZOMATO.STAGING.STG_REVIEWS
            WHERE COMMENT IS NOT NULL AND TRIM(COMMENT) <> ''
            ORDER BY RANDOM()
            LIMIT {NEW_REVIEWS}
        """
        df = conn.cursor().execute(query).fetch_pandas_all()
    finally:
        conn.close()

    df.columns = [col.lower() for col in df.columns]
    return df


def embed(texts, task_type):
    """Embed texts in small batches, waiting out free-tier rate limits."""
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        while True:
            try:
                response = client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    time.sleep(65)  # wait for the per-minute quota to reset
                else:
                    raise
        vectors.extend(e.values for e in response.embeddings)
        if i + BATCH_SIZE < len(texts):
            time.sleep(35)  # 50 texts per 35 seconds stays under 100/minute
    return vectors


@st.cache_data()
def load_reviews():
    if os.path.exists(CACHE_FILE):
        return pd.read_parquet(CACHE_FILE)

    df = read_reviews_from_snowflake()
    df["embedding"] = embed(df["comment"].tolist(), "RETRIEVAL_DOCUMENT")
    df.to_parquet(CACHE_FILE)
    return df


st.title("Chat with your Zomato Reviews")
st.caption(f"Searching {NEW_REVIEWS} reviews, answering with {CHAT_MODEL}")


def find_similar_reviews(question, df):
    question_vector = np.array(embed([question], "RETRIEVAL_QUERY")[0])
    review_matrix = np.array(df["embedding"].tolist())

    # cosine similarity of the question against every review at once
    scores = review_matrix @ question_vector / (
        np.linalg.norm(review_matrix, axis=1) * np.linalg.norm(question_vector)
    )

    df = df.copy()
    df["score"] = scores
    return df.nlargest(TOP_K, "score")


def ask_llm(question, top_reviews):
    context = ""
    for _, row in top_reviews.iterrows():
        context += f"({row['city']}, {row['rating']} stars) {row['comment']}\n"

    system_prompt = (
        "Answer ONLY using the customer reviews provided. "
        "Be concise. If the reviews don't cover it, say so."
    )
    user_prompt = f"Question: {question}\n\nReviews:\n{context}"

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    return response.text


review_df = load_reviews()

question = st.text_input(
    "Ask a question about your reviews:",
    placeholder="e.g. What are the most common complaints about delivery?",
)

if question:
    top_reviews = find_similar_reviews(question, review_df)
    answer = ask_llm(question, top_reviews)

    st.markdown("**Answer:**")
    st.write(answer)

    with st.expander("Reviews used to build this answer"):
        st.dataframe(top_reviews[["city", "rating", "comment"]], hide_index=True)