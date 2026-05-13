import re
import logging
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Download lexicon silently on first use
try:
    nltk.download('vader_lexicon', quiet=True)
except Exception:
    pass

logger = logging.getLogger(__name__)

# --- Singleton: VADER loads in milliseconds, not minutes ---
_vader = None

def get_vader():
    global _vader
    if _vader is None:
        _vader = SentimentIntensityAnalyzer()
        logger.info("PreprocessorAgent: VADER SentimentIntensityAnalyzer ready.")
    return _vader


class PreprocessorAgent:
    """
    Agent responsible for cleaning, standardizing, and augmenting fetched data.
    Uses VADER for fast, social-media-optimized sentiment analysis.

    Handles two comment schemas:
      - YouTube (FetcherAgent):  keys are source_id, parent_post_id, text, author, timestamp, platform
      - Apify (Meta platforms):  keys are source_id, parent_post_id, text, author, timestamp, platform
      - Legacy mock data:        keys are id, post_id, text, author, timestamp, platform

    VADER (Valence Aware Dictionary and sEntiment Reasoner):
    - Loads in milliseconds (no deep-learning model download needed)
    - Processes thousands of comments per second
    - Specifically tuned for social media text (handles emoji, slang, CAPS, etc.)
    - Produces a compound score in [-1, 1] which we normalise to [0, 1]
    """
    def __init__(self):
        self.vader = get_vader()

    def process(self, raw_comments: list) -> list:
        logger.info(f"PreprocessorAgent: Processing {len(raw_comments)} comments with VADER")
        processed_data = []

        for comment in raw_comments:
            # ── Normalise keys — support both schema variants ──────────────
            # Primary keys (YouTube + Apify): source_id / parent_post_id
            # Legacy / mock keys:             id        / post_id
            source_id   = comment.get("source_id")   or comment.get("id")   or ""
            parent_id   = comment.get("parent_post_id") or comment.get("post_id") or ""
            text        = comment.get("text") or comment.get("clean_text") or ""
            author      = comment.get("author") or "Unknown"
            timestamp   = comment.get("timestamp") or ""
            platform    = comment.get("platform") or "unknown"

            if not text:
                continue  # skip empty comments

            clean_text = self._clean_text(text)

            # VADER compound score: -1 (most negative) to +1 (most positive)
            scores = self.vader.polarity_scores(clean_text)
            compound = scores['compound']

            if compound >= 0.05:
                sentiment_label = 'positive'
                sentiment_score = (compound + 1) / 2   # map to [0.525, 1.0]
            elif compound <= -0.05:
                sentiment_label = 'negative'
                sentiment_score = (compound + 1) / 2   # map to [0.0, 0.475]
            else:
                sentiment_label = 'neutral'
                sentiment_score = 0.5

            processed_data.append({
                # Use unified keys so tasks.py storage works for all platforms
                "source_id":      source_id,
                "parent_post_id": parent_id,
                # Keep legacy aliases so any downstream code still works
                "id":      source_id,
                "post_id": parent_id,
                "original_text": text,
                "clean_text":    clean_text,
                "author":        author,
                "timestamp":     timestamp,
                "platform":      platform,
                "likes":         comment.get("raw_metrics", {}).get("likes", 0),
                "sentiment_label": sentiment_label,
                "sentiment_score": round(sentiment_score, 4),
                "keywords":        self._extract_keywords(clean_text),
            })

        logger.info(f"PreprocessorAgent: Done. {len(processed_data)} comments processed.")
        return processed_data

    def _clean_text(self, text: str) -> str:
        # Remove URLs
        text = re.sub(r'http\S+', '', text)
        # Remove HTML entities
        text = re.sub(r'&\w+;', ' ', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_keywords(self, text: str) -> list:
        words = text.lower().split()
        return [w for w in words if len(w) > 4 and w.isalpha()]
