from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True) # youtube, facebook, instagram
    source_id = Column(String, index=True) # ID of the post/video
    content_text = Column(Text)
    sentiment_score = Column(Float)
    sentiment_label = Column(String) # positive, negative, neutral
    created_at = Column(DateTime(timezone=True), server_default=func.now())
