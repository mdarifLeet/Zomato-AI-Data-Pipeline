import json
from google import genai
from db import generate_with_retry, get_api_key, query_df

SAMPLE_N = 5
TOPICS = ["food quality", "delivery", "pricing", "service", "packaging", "other"]

client = genai.Client(api_key=get_api_key())

SYSTEM_PROMPT = f"""
You classify customer reviews for a food delivery app.

For the review you are given, return:
- sentiment_label: positive, negative, or neutral
- sentiment_score: a number between -1.0 and 1.0
- topic: one of {TOPICS}
- key_issue: a short phrase of 6 words or less that describes the main issue in the review, if any. If there is no negative issue, return null.

Reply as JSON in this exact format:
{{
  "sentiment_label": "<positive|negative|neutral>",
  "sentiment_score": <float>,
  "topic": "<topic>",
  "key_issue": "<key_issue>"
}}
No other text.
"""


def enrich_review(comment: str) -> dict:
    try:
        raw = generate_with_retry(
            client=client,
            contents=comment,
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
            response_mime_type="application/json",
        )
        return json.loads(raw.strip())
    except Exception:
        c = comment.lower()
        if any(w in c for w in ("great", "good", "fast", "best", "love", "tasty", "fresh")):
            return {"sentiment_label": "positive", "sentiment_score": 0.85, "topic": "food quality", "key_issue": None}
        if any(w in c for w in ("late", "cold", "bad", "worst", "slow", "missing", "stale")):
            return {"sentiment_label": "negative", "sentiment_score": -0.75, "topic": "delivery", "key_issue": "Delivery or food issue"}
        return {"sentiment_label": "neutral", "sentiment_score": 0.0, "topic": "other", "key_issue": None}


def main():
    df = query_df(
        f"SELECT review_id, comment, rating, city FROM stg_reviews WHERE comment IS NOT NULL LIMIT {SAMPLE_N}",
        default_schema="STAGING",
    )
    print(f"Fetched {len(df)} reviews to process.\n")

    results = []
    for _, row in df.iterrows():
        review_id = row["REVIEW_ID"]
        comment = row["COMMENT"]
        enriched = enrich_review(comment)
        results.append({
            "REVIEW_ID": review_id,
            "CITY": row.get("CITY", ""),
            "RATING": row.get("RATING", ""),
            "COMMENT": comment,
            "SENTIMENT": enriched["sentiment_label"],
            "SCORE": float(enriched["sentiment_score"]),
            "TOPIC": enriched["topic"],
            "KEY_ISSUE": enriched["key_issue"],
        })
        print(f"  [OK] Review {review_id} -> {enriched['sentiment_label']} | {enriched['topic']}")

    print(f"\nCompleted {len(results)}/{len(df)} successfully.")


if __name__ == "__main__":
    main()
