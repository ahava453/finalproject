import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis Configuration for Celery Broker and Backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery explicitly pointing to our tasks
celery_app = Celery(
    "sentiment_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"] # Module containing our background tasks
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
