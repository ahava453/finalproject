from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import sys
import os
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from database import get_db, engine
from models import SentimentResult, Base
from tasks import run_sentiment_agent
from agents.visualizer import VisualizerAgent
from database import get_db
from sqlalchemy.orm import Session
from models import SentimentResult
from fastapi import Depends
from sqlalchemy import func

app = FastAPI(title="Multi-Agent Sentiment Analysis API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

from celery.result import AsyncResult
from celery_worker import celery_app


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Welcome to the Multi-Agent Insight API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


class AnalysisRequest(BaseModel):
    platform: str
    target_account: str
    api_key: str = ""           # YouTube Data API key
    max_videos: int = 50        # Max videos to scan per channel
    max_comments_per_video: int = 100  # Max comments collected per video
    apify_options: Optional[Dict[str, Any]] = None





@app.post("/api/analyze")
def trigger_analysis(request: AnalysisRequest):
    """Trigger the Multi-Agent Pipeline via Celery."""
    # For YouTube: api_key is the YT Data API key.
    # For Facebook/Instagram: api_key is the Apify token (optional — falls back to .env).
    api_keys = {
        request.platform: request.api_key,
        # Always populate both meta keys so the fetcher can pick up the token
        # regardless of whether the user is on the facebook or instagram tab.
        "facebook": request.api_key if request.platform in ("facebook", "instagram") else "",
        "instagram": request.api_key if request.platform in ("facebook", "instagram") else "",
        # Optional: pass through arbitrary Apify options (proxy/session/cookies)
        "apify_options": request.apify_options or {},
    }

    task = run_sentiment_agent.delay(
        request.platform,
        request.target_account,
        api_keys,
        request.max_videos,
        request.max_comments_per_video,
    )

    return {
        "message": (
            f"Multi-Agent pipeline dispatched for {request.platform} "
            f"account '{request.target_account}'"
        ),
        "job_id": task.id,
    }


@app.get("/api/task-status/{job_id}")
def get_task_status(job_id: str):
    """Returns the current background task state from Celery."""
    task_result = AsyncResult(job_id, app=celery_app)
    
    # Format to match the frontend expectations
    state = {
        "running": not task_result.ready(),
        "done": task_result.ready(),
        "error": None,
        "processed": 0,
        "job_id": job_id,
        "status_message": "Initializing..."
    }
    
    if task_result.info and isinstance(task_result.info, dict):
        state["processed"] = task_result.info.get("processed", 0)
        state["status_message"] = task_result.info.get("status", state["status_message"])
        # If the task returned an error payload (logged as a successful task returning an error dict),
        # surface it to the frontend so users see the reason instead of a silent timeout.
        if task_result.info.get("status") == "error":
            state["error"] = task_result.info.get("message")
        
    if task_result.state == "FAILURE":
        state["error"] = str(task_result.info)
    elif task_result.state == "SUCCESS" and isinstance(task_result.info, dict):
        state["processed"] = task_result.info.get("processed_reviews", 0)
        
    return state


@app.get("/api/count/{platform}")
def get_comment_count(platform: str, db: Session = Depends(get_db)):
    """Return the total number of stored comments for a platform."""
    count = db.query(SentimentResult).filter(SentimentResult.platform == platform).count()
    return {"platform": platform, "count": count}


@app.delete("/api/data/{platform}")
def clear_platform_data(platform: str, db: Session = Depends(get_db)):
    """Delete all stored comments for a given platform."""
    deleted = db.query(SentimentResult).filter(SentimentResult.platform == platform).delete()
    db.commit()
    return {"message": f"Cleared {deleted} records for '{platform}'."}

# ── Meta Integration Routes ──────────────────────────────────────────────────

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import os
from dotenv import load_dotenv

@app.get("/api/auth/meta")
def auth_meta():
    """Redirect user to Meta OAuth login."""
    load_dotenv(override=True)
    FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID")
    FACEBOOK_REDIRECT_URI = os.environ.get("FACEBOOK_REDIRECT_URI", "http://localhost:8000/api/auth/meta/callback")
    
    if not FACEBOOK_APP_ID:
        raise HTTPException(status_code=500, detail="FACEBOOK_APP_ID is not configured in the .env file.")
    oauth_url = f"https://www.facebook.com/v19.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={FACEBOOK_REDIRECT_URI}&scope=pages_show_list,instagram_basic,instagram_manage_comments,pages_read_engagement"
    return RedirectResponse(oauth_url)

@app.get("/api/auth/meta/callback")
def auth_meta_callback(code: str = None):
    """Handle Meta OAuth callback and exchange code for short-lived token."""
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")
    return {"message": "OAuth successful. Code received.", "code": code}

@app.get("/webhook/meta")
def verify_meta_webhook(request: Request):
    """Meta Webhook Handshake Verification."""
    # Load verification token from environment (safe default for local testing)
    load_dotenv(override=False)
    META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "mock_verify_token")

    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == META_VERIFY_TOKEN:
            try:
                return int(challenge)
            except Exception:
                return challenge
        raise HTTPException(status_code=403, detail="Verification failed")
    raise HTTPException(status_code=400, detail="Missing parameters")

from tasks import process_webhook_event

@app.post("/webhook/meta")
async def handle_meta_webhook(request: Request):
    """Receive live events from Meta Webhooks and dispatch to Celery."""
    payload = await request.json()
    if payload.get("object") in ["page", "instagram"]:
        # Dispatch to async queue
        process_webhook_event.delay(payload)
        return {"status": "EVENT_RECEIVED"}
    raise HTTPException(status_code=404, detail="Unrecognized object type")



@app.get("/api/dashboard/{platform}")
def get_dashboard_data(platform: str, db: Session = Depends(get_db)):
    """Fetch results and pass them through VisualizerAgent for frontend prep."""
    results = (
        db.query(SentimentResult)
        .filter(SentimentResult.platform == platform)
        .order_by(SentimentResult.created_at.desc())
        .limit(500)
        .all()
    )

    if not results:
        # Return an empty but valid dashboard structure
        visualizer = VisualizerAgent()
        return visualizer.generate_dashboard_data([])

    processed_comments = [
        {
            "id": r.source_id,
            "platform": r.platform,
            "clean_text": r.content_text,
            "sentiment_score": r.sentiment_score,
            "sentiment_label": r.sentiment_label,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "keywords": [],
        }
        for r in results
    ]

    visualizer = VisualizerAgent()
    dashboard_data = visualizer.generate_dashboard_data(processed_comments)
    return dashboard_data


@app.get("/api/report")
def cross_platform_report(db: Session = Depends(get_db)):
    """Aggregated cross-platform sentiment report by platform and content_type."""
    rows = (
        db.query(
            SentimentResult.platform,
            SentimentResult.content_type,
            func.count(SentimentResult.id).label("count"),
            func.avg(SentimentResult.sentiment_score).label("avg_sentiment"),
        )
        .group_by(SentimentResult.platform, SentimentResult.content_type)
        .all()
    )

    report = {}
    for platform, content_type, count, avg in rows:
        report.setdefault(platform, {})[content_type or "unknown"] = {
            "count": int(count),
            "avg_sentiment": float(avg) if avg is not None else None,
        }

    return {"report": report}
