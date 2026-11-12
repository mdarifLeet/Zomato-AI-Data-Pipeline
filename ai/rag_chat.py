import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from google import genai
from db import generate_with_retry, get_api_key, query_df

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
NEW_REVIEWS = 100
TOP_K = 5
BATCH_SIZE = 50
CACHE_FILE = Path(__file__).resolve().parent / "review_embeddings.parquet"

EXAMPLE_REVIEW_QUESTIONS = [
    "What do customers say about delivery speed?",
    "Are customers happy with value for price?",
    "What complaints do customers have about food quality?",
    "How is the service in Bangalore?",
]

client = genai.Client(api_key=get_api_key())


@st.cache_data(show_spinner="Loading review embeddings...")
def load_and_embed_reviews():
    if CACHE_FILE.exists():
        df = pd.read_parquet(CACHE_FILE)
        df.columns = ["embedding" if c.lower() == "embedding" else c.upper() for c in df.columns]
        if "RATING" not in df.columns or "CITY" not in df.columns:
            try:
                meta = query_df(
                    "SELECT review_id, rating, city FROM stg_reviews",
                    default_schema="STAGING",
                )
                df = df.drop(columns=[c for c in ("RATING", "CITY") if c in df.columns])
                df = df.merge(meta, on="REVIEW_ID", how="left")
                df.to_parquet(CACHE_FILE, index=False)
            except Exception:
                if "RATING" not in df.columns:
                    df["RATING"] = "N/A"
                if "CITY" not in df.columns:
                    df["CITY"] = "N/A"
        df["embedding"] = df["embedding"].apply(lambda x: np.array(x, dtype=np.float32))
        return df

    df = query_df(
        f"SELECT review_id, comment, rating, city FROM stg_reviews WHERE comment IS NOT NULL LIMIT {NEW_REVIEWS}",
        default_schema="STAGING",
    )

    embeddings = []
    comments = df["COMMENT"].tolist()
    for i in range(0, len(comments), BATCH_SIZE):
        batch = comments[i : i + BATCH_SIZE]
        resp = client.models.embed_content(model=EMBEDDING_MODEL, contents=batch)
        for e in resp.embeddings:
            embeddings.append(e.values)

    df["embedding"] = embeddings
    df.to_parquet(CACHE_FILE, index=False)
    df["embedding"] = df["embedding"].apply(lambda x: np.array(x, dtype=np.float32))
    return df


def search_reviews(query: str, df: pd.DataFrame, top_k: int = TOP_K):
    resp = client.models.embed_content(model=EMBEDDING_MODEL, contents=query)
    query_emb = np.array(resp.embeddings[0].values, dtype=np.float32)

    matrix = np.vstack(df["embedding"].values)
    scores = np.dot(matrix, query_emb) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_emb))

    top_idx = np.argsort(scores)[::-1][:top_k]
    matched = df.iloc[top_idx].copy()
    matched["score"] = scores[top_idx]
    return matched


def rag_answer(query: str, context_df: pd.DataFrame) -> str:
    context = "\n\n".join([
        f"Rating: {row.get('RATING', 'N/A')}/5 | City: {row.get('CITY', 'N/A')}\nReview: {row.get('COMMENT', '')}"
        for _, row in context_df.iterrows()
    ])

    prompt = f"""
    Answer the user's question using only the context reviews provided below.
    If the context does not contain enough information, say so clearly.

    Context:
    {context}

    Question: {query}
    """
    try:
        return generate_with_retry(client=client, contents=prompt, temperature=0.2)
    except Exception:
        avg_rating = pd.to_numeric(context_df["RATING"], errors="coerce").mean()
        cities = ", ".join(context_df["CITY"].dropna().astype(str).unique()[:4])
        top_comments = "; ".join(context_df["COMMENT"].dropna().astype(str).head(3).tolist())
        return (
            f"Based on the top {len(context_df)} matching reviews (average rating {avg_rating:.1f}/5 "
            f"across {cities}): {top_comments}"
        )


def main():
    st.set_page_config(page_title="Zomato Review RAG Chat", layout="wide")
    st.title("Zomato Customer Review Search & Q&A")

    df = load_and_embed_reviews()
    st.success(f"Loaded {len(df)} review embeddings.")

    st.subheader("Example Questions")
    cols = st.columns(len(EXAMPLE_REVIEW_QUESTIONS))
    if "rag_question" not in st.session_state:
        st.session_state["rag_question"] = ""
    for idx, q in enumerate(EXAMPLE_REVIEW_QUESTIONS):
        if cols[idx].button(q):
            st.session_state["rag_question"] = q

    query = st.text_input(
        "Ask a question about customer reviews:",
        key="rag_question",
        placeholder="e.g. What are customers saying about food delivery in Bangalore?",
    )

    if query:
        matches = search_reviews(query, df)
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Relevant Reviews")
            for _, row in matches.iterrows():
                st.markdown(f"**Rating:** {row.get('RATING', 'N/A')} | **City:** {row.get('CITY', 'N/A')} | **Similarity:** {row['score']:.2f}")
                st.write(row.get("COMMENT", ""))
                st.divider()

        with col2:
            st.subheader("AI Answer")
            with st.spinner("Generating answer..."):
                answer = rag_answer(query, matches)
                st.write(answer)


if __name__ == "__main__":
    main()
