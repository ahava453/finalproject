from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InternalCommentSchema(BaseModel):
    """Unified schema for cross-platform data normalization."""
    platform: str
    source_id: str
    parent_post_id: Optional[str] = None
    author: Optional[str] = None
    text: str
    timestamp: Optional[datetime] = None

class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True) # youtube, facebook, instagram
    source_id = Column(String, index=True) # ID of the specific comment
    parent_post_id = Column(String, index=True, nullable=True) # ID of the video or post
    content_text = Column(Text)
    sentiment_score = Column(Float)
    sentiment_label = Column(String) # positive, negative, neutral
    content_type = Column(String, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
