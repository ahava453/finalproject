from database import SessionLocal
from models import SentimentResult
import sys
import os
import logging
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_sentiment_agent(platform: str, target_account: str, api_keys: dict):
    """
    Multi-Agent Workflow:
    1. Fetching Agent: Retrieves comments from social platforms.
    2. Processing Agent: Cleans text, extracts keywords, and scores sentiment.
    3. Storage: Saves results to DB.
    """
    logger.info(f"[TASK START] platform={platform}, account={target_account}")

    # ── Import agents here so reload picks up changes ──────────────────
    try:
        from agents.fetcher import FetcherAgent
        from agents.preprocessor import PreprocessorAgent
        logger.info("[TASK] Agent imports OK")
    except Exception as exc:
        logger.error(f"[TASK] Agent import FAILED: {exc}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(exc)}

    # ── 1. Fetch ────────────────────────────────────────────────────────
    try:
        fetcher = FetcherAgent(api_keys=api_keys)
        logger.info("[TASK] Fetcher initialised, calling fetch_comments...")
        raw_comments = fetcher.fetch_comments(platform, target_account)
        logger.info(f"[TASK] Fetch done. Got {len(raw_comments)} comments.")
    except Exception as exc:
        logger.error(f"[TASK] Fetch FAILED: {exc}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(exc)}

    if not raw_comments:
        logger.info("[TASK] No comments returned. Exiting.")
        return {"status": "success", "message": "No comments found.", "processed": 0}

    # ── 2. Preprocess ───────────────────────────────────────────────────
    try:
        preprocessor = PreprocessorAgent()
        logger.info(f"[TASK] Preprocessor ready. Processing {len(raw_comments)} comments...")
        processed_comments = preprocessor.process(raw_comments)
        logger.info(f"[TASK] Preprocessing done. {len(processed_comments)} processed.")
    except Exception as exc:
        logger.error(f"[TASK] Preprocess FAILED: {exc}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(exc)}

    # ── 3. Storage ──────────────────────────────────────────────────────
    db = SessionLocal()
    processed_count = 0
    try:
        for comment in processed_comments:
            # Skip duplicates
            exists = db.query(SentimentResult).filter_by(source_id=comment["id"]).first()
            if exists:
                continue
            new_result = SentimentResult(
                platform=platform,
                source_id=comment["id"],
                content_text=comment["clean_text"],
                sentiment_score=comment["sentiment_score"],
                sentiment_label=comment["sentiment_label"]
            )
            db.add(new_result)
            processed_count += 1

        db.commit()
        logger.info(f"[TASK] Saved {processed_count} new results to DB.")
    except Exception as exc:
        db.rollback()
        logger.error(f"[TASK] DB write FAILED: {exc}\n{traceback.format_exc()}")
    finally:
        db.close()

    logger.info(f"[TASK DONE] Processed {processed_count} comments for {platform}.")
    return {"status": "success", "processed_reviews": processed_count, "platform": platform}
