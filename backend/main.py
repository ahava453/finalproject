from pydantic import BaseModel
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

app = FastAPI(title="Multi-Agent Sentiment Analysis API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# ── In-memory task state ────────────────────────────────────────────────────
# Tracks the latest background job so the frontend can poll for completion
# without relying purely on DB row counts (which stay the same when all
# comments are duplicates).
_task_lock = threading.Lock()
_task_state: dict = {
    "running": False,
    "done": False,
    "error": None,
    "processed": 0,
    "job_id": None,
}

def _get_state() -> dict:
    with _task_lock:
        return dict(_task_state)

def _set_state(**kwargs):
    with _task_lock:
        _task_state.update(kwargs)


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


def _run_task_with_state(
    platform, target_account, api_keys, max_videos, max_comments_per_video
):
    """Wraps run_sentiment_agent to update _task_state on start/finish/error."""
    _set_state(running=True, done=False, error=None, processed=0)
    try:
        result = run_sentiment_agent(
            platform, target_account, api_keys, max_videos, max_comments_per_video
        )
        processed = result.get("processed_reviews", 0) if isinstance(result, dict) else 0
        _set_state(running=False, done=True, error=None, processed=processed)
    except Exception as exc:
        _set_state(running=False, done=True, error=str(exc), processed=0)


@app.post("/api/analyze")
def trigger_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Trigger the Multi-Agent Pipeline to process data."""
    import uuid
    job_id = str(uuid.uuid4())
    _set_state(running=True, done=False, error=None, processed=0, job_id=job_id)

    api_keys = {request.platform: request.api_key}
    background_tasks.add_task(
        _run_task_with_state,
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
        "job_id": job_id,
    }


@app.get("/api/task-status")
def get_task_status():
    """Returns the current background task state."""
    return _get_state()


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
