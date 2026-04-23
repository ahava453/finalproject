import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class VisualizerAgent:
    """
    Agent responsible for aggregating processed data into chart-ready formats.
    """

    def generate_dashboard_data(self, processed_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info(f"VisualizerAgent: Aggregating {len(processed_comments)} comments")

        if not processed_comments:
            return self._empty_dashboard()

        # ── 1. Sentiment Distribution ──────────────────────────────────────
        sentiment_counts = Counter(c["sentiment_label"] for c in processed_comments)

        # ── 2. Platform Distribution ───────────────────────────────────────
        platform_counts = Counter(c["platform"] for c in processed_comments)

        # ── 3. Top Keywords ────────────────────────────────────────────────
        all_keywords: list = []
        for c in processed_comments:
            all_keywords.extend(c.get("keywords", []))
        top_keywords = Counter(all_keywords).most_common(10)

        # ── 4. Real Sentiment Timeline ─────────────────────────────────────
        # Group comments by date (YYYY-MM-DD) using the created_at field.
        # Falls back to a flat single-bucket if timestamps are missing.
        day_buckets: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
        )

        for c in processed_comments:
            raw_ts = c.get("created_at") or c.get("timestamp") or ""
            # Extract just the date portion (first 10 chars of ISO string)
            date_key = raw_ts[:10] if len(raw_ts) >= 10 else "Unknown"
            label = c.get("sentiment_label", "neutral")
            day_buckets[date_key][label] = day_buckets[date_key].get(label, 0) + 1
            day_buckets[date_key]["total"] += 1

        # Sort chronologically; limit to last 14 days for readability
        sorted_dates = sorted(day_buckets.keys())[-14:]
        sentiment_timeline = [
            {
                "date": d,
                "positive": day_buckets[d].get("positive", 0),
                "negative": day_buckets[d].get("negative", 0),
                "neutral":  day_buckets[d].get("neutral",  0),
            }
            for d in sorted_dates
        ]

        # ── 5. Average sentiment score ─────────────────────────────────────
        avg_sentiment = sum(c.get("sentiment_score", 0.5) for c in processed_comments) / len(
            processed_comments
        )
        
        # ── 6. Business Intelligence Summary ───────────────────────────────
        positive_pct = round(sentiment_counts.get("positive", 0) / len(processed_comments) * 100, 1)
        negative_pct = round(sentiment_counts.get("negative", 0) / len(processed_comments) * 100, 1)
        
        platforms = list(platform_counts.keys())
        platform_str = " across " + " and ".join(platforms) if platforms else ""
        
        bi_summary = f"Sentiment{platform_str} is {positive_pct}% positive."
        if negative_pct > 20:
            bi_summary += f" However, {sentiment_counts.get('negative', 0)} comments expressed negative feedback that should be reviewed."
        elif top_keywords:
            top_word = top_keywords[0][0]
            bi_summary += f" The most frequently mentioned keyword is '{top_word}'."

        return {
            "summary": {
                "total_comments": len(processed_comments),
                "avg_sentiment": round(avg_sentiment, 4),
                "positive_pct": positive_pct,
                "negative_pct": negative_pct,
                "bi_summary": bi_summary,
            },
            "charts": {
                "sentiment_pie": [
                    {"name": "Positive", "value": sentiment_counts.get("positive", 0)},
                    {"name": "Neutral",  "value": sentiment_counts.get("neutral",  0)},
                    {"name": "Negative", "value": sentiment_counts.get("negative", 0)},
                ],
                "platform_bar": [
                    {"name": k, "value": v} for k, v in platform_counts.items()
                ],
                "keyword_cloud": [
                    {"text": k, "value": v} for k, v in top_keywords
                ],
                "sentiment_timeline": sentiment_timeline,
            },
            "raw_samples": processed_comments[:100],
        }

    def _empty_dashboard(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_comments": 0,
                "avg_sentiment": 0.5,
                "positive_pct": 0.0,
                "negative_pct": 0.0,
            },
            "charts": {
                "sentiment_pie": [],
                "platform_bar": [],
                "keyword_cloud": [],
                "sentiment_timeline": [],
            },
            "raw_samples": [],
        }
