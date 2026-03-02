import time
import random
import time
import random
from transformers import pipeline
from database import SessionLocal
from models import SentimentResult

# Initialize the DistilBERT sentiment analysis pipeline once when the module loads
print("Loading HuggingFace DistilBERT model...")
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

def run_sentiment_agent(platform: str, api_key: str):
    """
    Synchronous Agent Workflow (removed Celery dependency for simplicity):
    1. Fetching Agent: Simulates fetching data from the platform.
    2. Processing Agent: Analyzes text sentiment using DistilBERT.
    3. Storage Agent: Saves results to SQLite DB.
    """
    # 1. Simulate Fetching Data
    time.sleep(1) # Simulate network delay
    
    mock_reviews = [
        "This product is absolutely amazing! Highly recommended.",
        "Terrible experience, would not buy again.",
        "It's okay, nothing special but it works as expected.",
        "Love the new design! So sleek.",
        "Customer service was completely unhelpful."
    ]
    sampled_reviews = random.sample(mock_reviews, 3)

    db = SessionLocal()
    processed_count = 0

    try:
        # 2. NLP Processing with DistilBERT
        for review in sampled_reviews:
            # The pipeline returns a list of dicts like: [{'label': 'POSITIVE', 'score': 0.99}]
            result = sentiment_pipeline(review)[0]
            
            label_mapping = {
                "POSITIVE": "positive",
                "NEGATIVE": "negative"
            }
            mapped_label = label_mapping.get(result['label'], "neutral")
            
            # 3. Save to Database
            new_result = SentimentResult(
                platform=platform,
                source_id=f"mock_{random.randint(1000, 9999)}",
                content_text=review,
                sentiment_score=result['score'],
                sentiment_label=mapped_label
            )
            db.add(new_result)
            processed_count += 1
            
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

    return {"status": "success", "processed_reviews": processed_count, "platform": platform}
