import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# SQLite Database URL
DATABASE_URL = "sqlite:///./sql_app.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema():
    """Ensure existing SQLite tables have required columns added."""
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        known_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(sentiment_results)"))}
        if not known_cols:
            return

        missing_columns = []
        if "parent_post_id" not in known_cols:
            missing_columns.append("parent_post_id VARCHAR")
        if "content_type" not in known_cols:
            missing_columns.append("content_type VARCHAR")

        for column_def in missing_columns:
            conn.execute(text(f"ALTER TABLE sentiment_results ADD COLUMN {column_def}"))
