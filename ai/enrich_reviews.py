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
    raw = generate_with_retry(
        client=client,
        contents=comment,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.0,
        response_mime_type="application/json",
    )
    return json.loads(raw.strip())


def main():
    df = query_df(
        f"SELECT review_id, comment FROM stg_reviews WHERE comment IS NOT NULL LIMIT {SAMPLE_N}",
        default_schema="STAGING",
    )
    print(f"Fetched {len(df)} reviews to process.\n")

    results = []
    for _, row in df.iterrows():
        review_id = row["REVIEW_ID"]
        comment = row["COMMENT"]
        try:
            enriched = enrich_review(comment)
            results.append((
                review_id,
                enriched["sentiment_label"],
                float(enriched["sentiment_score"]),
                enriched["topic"],
                enriched["key_issue"],
            ))
            print(f"  [OK] Review {review_id} -> {enriched['sentiment_label']} | {enriched['topic']}")
        except Exception as e:
            print(f"  [ERR] Review {review_id} failed: {e}")

    print(f"\nCompleted {len(results)}/{len(df)} successfully.")


if __name__ == "__main__":
    main()
