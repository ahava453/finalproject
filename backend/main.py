from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sentiment Analysis API", version="1.0.0")

# Configure CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Sentiment Analysis Backend API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends, BackgroundTasks
from tasks import run_sentiment_agent
from database import get_db, engine
from models import SentimentResult, Base

# Create database tables automatically
Base.metadata.create_all(bind=engine)

class AnalysisRequest(BaseModel):
    platform: str
    api_key: str

@app.post("/api/analyze")
def trigger_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Trigger the AI Agents to start running in the background via FastAPI BackgroundTasks."""
    background_tasks.add_task(run_sentiment_agent, request.platform, request.api_key)
    return {"message": "Analysis started in background"}

@app.get("/api/results/{platform}")
def get_results(platform: str, db: Session = Depends(get_db)):
    """Fetch the analyzed sentiment results from the database."""
    results = db.query(SentimentResult).filter(SentimentResult.platform == platform).order_by(SentimentResult.created_at.desc()).limit(20).all()
    return {"platform": platform, "results": results}

