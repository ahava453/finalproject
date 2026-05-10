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
import threading
import time

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
        # Start a heartbeat thread to periodically update Celery task state
        # This prevents the frontend from assuming the backend has stalled
        # during long-running fetches (YouTube channel scans, Apify runs, etc.).
        stop_event = threading.Event()
        def _heartbeat():
            interval = 5
            while not stop_event.is_set():
                try:
                    self.update_state(state='PROGRESS', meta={'status': f'Fetching {platform} comments... still working', 'processed': 0})
                except Exception:
                    pass
                time.sleep(interval)

        hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        hb_thread.start()

        # Give the UI immediate feedback before the (potentially slow) Apify call
        if platform in ("facebook", "instagram"):
            self.update_state(
                state='PROGRESS',
                meta={'status': f'Scraping {platform} comments via Apify... this may take 30-60 seconds.', 'processed': 0}
            )
        elif platform == "youtube":
            # Inform the UI that we're performing a deep fetch across Shorts and long-form videos
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Agent is fetching comments from Reels and Shorts...', 'processed': 0}
            )

        try:
            raw_comments = fetcher.fetch_comments(
                platform,
                target_account,
                max_comments_per_video=max_comments_per_video,
                max_videos=max_videos,
            )
        finally:
            # Stop heartbeat once fetch returns (or errors)
            stop_event.set()

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

    # ── 2.b Deep (BERT) analysis ──────────────────────────────────────
    try:
        from agents.analyzer import SentimentAnalyzerAgent
        try:
            analyzer = SentimentAnalyzerAgent()
            logger.info("[TASK] Analyzer initialised — running BERT inference on cleaned texts.")
            for comment in processed_comments:
                try:
                    res = analyzer.analyze_text(comment.get('clean_text', ''))
                    lbl = str(res.get('label', '')).upper()
                    if 'POSITIVE' in lbl:
                        comment['sentiment_label'] = 'positive'
                    elif 'NEGATIVE' in lbl:
                        comment['sentiment_label'] = 'negative'
                    else:
                        comment['sentiment_label'] = 'neutral'
                    comment['sentiment_score'] = float(res.get('score', 0.5))
                    comment['bert_label'] = res.get('label')
                    comment['bert_score'] = res.get('score')
                except Exception as e:
                    logger.warning(f"[TASK] BERT inference failed for a comment: {e}")
        except Exception as e:
            logger.error(f"[TASK] Analyzer initialization failed: {e}")
    except Exception:
        # analyzer is optional — continue even if unavailable
        logger.info("[TASK] AnalyzerAgent not available; skipping deep model inference.")

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
                content_type=comment.get("content_type"),
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
    entries = payload.get("entry", []) or []

    raw_comments = []
    import uuid
    for entry in entries:
        changes = entry.get("changes", []) or []
        for change in changes:
            field = change.get("field") or ""
            value = change.get("value", {}) or {}
            logger.debug(f"[WEBHOOK TASK] change field={field} value_keys={list(value.keys())}")

            # Common shapes: Facebook Page feed comments, Instagram comments
            # Try to extract known fields across different webhook formats.
            comment_id = (
                value.get("comment_id")
                or value.get("id")
                or value.get("commentId")
            )
            text = (
                value.get("message")
                or value.get("text")
                or value.get("message_text")
                or value.get("comment_text")
            )
            parent_id = (
                value.get("post_id")
                or value.get("parent_id")
                or value.get("media_id")
                or value.get("postId")
            )
            author = None
            if isinstance(value.get("from"), dict):
                author = value.get("from").get("name") or value.get("from").get("username")
            author = author or value.get("sender_name") or value.get("username") or "Unknown"
            timestamp = value.get("created_time") or value.get("created_at") or value.get("timestamp")

            # If we have either an explicit comment id or some textual content, accept it.
            if comment_id or text:
                if not comment_id:
                    comment_id = f"webhook-{uuid.uuid4().hex}"

                raw_comments.append({
                    "platform": platform,
                    "source_id": str(comment_id),
                    "parent_post_id": str(parent_id) if parent_id is not None else None,
                    "author": author,
                    "text": text or "",
                    "timestamp": str(timestamp) if timestamp is not None else "",
                })

    if not raw_comments:
        logger.info("[WEBHOOK TASK] No comment-like entries found in webhook payload.")
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
        saved = 0
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
            saved += 1
        db.commit()
        logger.info(f"[WEBHOOK TASK] Saved {saved} real-time comments to DB.")
    except Exception as exc:
        db.rollback()
        logger.error(f"[WEBHOOK TASK] DB write FAILED: {exc}")
    finally:
        db.close()
    return {"status": "success"}
