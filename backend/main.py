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





@app.post("/api/analyze")
def trigger_analysis(request: AnalysisRequest):
    """Trigger the Multi-Agent Pipeline via Celery."""
    api_keys = {request.platform: request.api_key}
    
    # Dispatch task to Celery
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
