from database import SessionLocal
from models import SentimentResult
import sys
import os
import logging
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from celery_worker import celery_app

@celery_app.task(bind=True)
def run_sentiment_agent(
    self,
    platform: str,
    target_account: str,
    api_keys: dict,
    max_videos: int = 50,
    max_comments_per_video: int = 100,
):
    """
    Multi-Agent Workflow:
    1. Fetching Agent  – retrieves comments from social platforms.
    2. Processing Agent – cleans text, extracts keywords, scores sentiment.
    3. Storage          – saves results to DB.

    For YouTube:
      - If `target_account` is a single video URL/ID  → fetches up to
        `max_comments_per_video` comments for that video.
      - If `target_account` is a channel URL/@handle/UCxxx ID → fetches
        comments across ALL videos in the channel (up to `max_videos` videos,
        `max_comments_per_video` comments each).
    """
    logger.info(
        f"[TASK START] platform={platform}, account={target_account}, "
        f"max_videos={max_videos}, max_comments_per_video={max_comments_per_video}"
    )

    # ── Import agents here so reload picks up changes ──────────────────
    try:
        from agents.fetcher import FetcherAgent
        from agents.preprocessor import PreprocessorAgent
        logger.info("[TASK] Agent imports OK")
    except Exception as exc:
        logger.error(f"[TASK] Agent import FAILED: {exc}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(exc)}

    # ── 1. Fetch ────────────────────────────────────────────────────────────
    try:
        fetcher = FetcherAgent(api_keys=api_keys)
        logger.info("[TASK] Fetcher initialised, calling fetch_comments...")

        # Give the UI immediate feedback before the (potentially slow) Apify call
        if platform in ("facebook", "instagram"):
            self.update_state(
                state='PROGRESS',
                meta={'status': f'Scraping {platform} comments via Apify... this may take 30-60 seconds.', 'processed': 0}
            )

        raw_comments = fetcher.fetch_comments(
            platform,
            target_account,
            max_comments_per_video=max_comments_per_video,
            max_videos=max_videos,
        )
        self.update_state(state='PROGRESS', meta={'status': f'Fetched {len(raw_comments)} comments. Preprocessing...', 'processed': 0})
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
        self.update_state(state='PROGRESS', meta={'status': f'Preprocessed {len(processed_comments)} comments. Saving to DB...', 'processed': 0})
        logger.info(f"[TASK] Preprocessing done. {len(processed_comments)} processed.")
    except Exception as exc:
        logger.error(f"[TASK] Preprocess FAILED: {exc}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(exc)}

    # ── 3. Storage ──────────────────────────────────────────────────────
    db = SessionLocal()
    processed_count = 0
    try:
        for comment in processed_comments:
            # Handle new and old keys gracefully
            src_id = comment.get("source_id", comment.get("id"))
            parent_id = comment.get("parent_post_id", comment.get("post_id"))
            
            # Skip duplicates
            exists = db.query(SentimentResult).filter_by(source_id=src_id).first()
            if exists:
                continue
            new_result = SentimentResult(
                platform=platform,
                source_id=src_id,
                parent_post_id=parent_id,
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

@celery_app.task(bind=True)
def process_webhook_event(self, payload: dict):
    """Processes real-time events from Meta Webhooks."""
    logger.info(f"[WEBHOOK TASK] Processing payload: {payload}")
    platform = payload.get("object", "unknown")
    entries = payload.get("entry", [])
    
    raw_comments = []
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            if change.get("field") == "comments" and value.get("item") == "comment":
                raw_comments.append({
                    "platform": platform,
                    "source_id": value.get("comment_id"),
                    "parent_post_id": value.get("post_id"),
                    "author": value.get("from", {}).get("name", "Unknown"),
                    "text": value.get("message", ""),
                    "timestamp": str(value.get("created_time", ""))
                })
                
    if not raw_comments:
        return {"status": "success", "message": "No comments found in webhook payload."}
        
    try:
        from agents.preprocessor import PreprocessorAgent
        preprocessor = PreprocessorAgent()
        processed_comments = preprocessor.process(raw_comments)
    except Exception as exc:
        logger.error(f"[WEBHOOK TASK] Preprocess FAILED: {exc}")
        return {"status": "error"}
        
    db = SessionLocal()
    try:
        for comment in processed_comments:
            src_id = comment.get("source_id")
            if db.query(SentimentResult).filter_by(source_id=src_id).first():
                continue
            db.add(SentimentResult(
                platform=platform,
                source_id=src_id,
                parent_post_id=comment.get("parent_post_id"),
                content_text=comment["clean_text"],
                sentiment_score=comment["sentiment_score"],
                sentiment_label=comment["sentiment_label"]
            ))
        db.commit()
        logger.info(f"[WEBHOOK TASK] Saved {len(processed_comments)} real-time comments to DB.")
    except Exception as exc:
        db.rollback()
        logger.error(f"[WEBHOOK TASK] DB write FAILED: {exc}")
    finally:
        db.close()
    return {"status": "success"}
