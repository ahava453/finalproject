from pydantic import BaseModel
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, Depends, BackgroundTasks
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

@app.get("/")
def read_root():
    return {"message": "Welcome to the Multi-Agent Insight API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


class AnalysisRequest(BaseModel):
    platform: str
    target_account: str
    api_key: str = "" # Optional/dummy for now

@app.post("/api/analyze")
def trigger_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Trigger the Multi-Agent Pipeline to process data."""
    api_keys = {request.platform: request.api_key}
    background_tasks.add_task(run_sentiment_agent, request.platform, request.target_account, api_keys)
    return {"message": f"Multi-Agent pipeline dispatched for {request.platform} account {request.target_account}"}

@app.get("/api/dashboard/{platform}")
def get_dashboard_data(platform: str, db: Session = Depends(get_db)):
    """Fetch results and pass them through VisualizerAgent for frontend prep."""
    results = db.query(SentimentResult).filter(SentimentResult.platform == platform).order_by(SentimentResult.created_at.desc()).limit(100).all()
    
    # Re-format from DB models back to dict for the Visualizer
    processed_comments = [
        {
            "id": r.source_id,
            "platform": r.platform,
            "clean_text": r.content_text,
            "sentiment_score": r.sentiment_score,
            "sentiment_label": r.sentiment_label,
            "keywords": [] # Usually stored in DB, mocking empty for DB retrocompatibility
        } for r in results
    ]
    
    # Visualizer Agent aggregates data into beautiful structured charts
    visualizer = VisualizerAgent()
    dashboard_data = visualizer.generate_dashboard_data(processed_comments)
    return dashboard_data


