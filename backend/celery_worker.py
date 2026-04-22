import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# We use SQLite for the broker and the result backend to ensure 
# this works out-of-the-box on Windows without installing Redis!
BROKER_URL = "sqla+sqlite:///./celery_broker.sqlite"
BACKEND_URL = "db+sqlite:///./celery_results.sqlite"

# Initialize Celery explicitly pointing to our tasks
celery_app = Celery(
    "sentiment_worker",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["tasks"] # Module containing our background tasks
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # This prevents SQLite locking issues for the broker:
    broker_pool_limit=None, 
)
