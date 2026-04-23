# Project Viva & End-to-End Process Guide
**Multi-Agent Real-Time Sentiment Analysis — AgentFlow**

This document is your ultimate Viva (oral examination) preparation guide. It traces data through the full pipeline and provides precise answers to questions an external examiner is highly likely to ask.

---

## 🏗️ 1. Step-by-Step Flow (How it actually works)

Let's trace a piece of data from the moment the user clicks "Run Analysis" to the moment a chart appears.

### **Step 1: The User Request (Frontend — React + Vite)**
- The user opens the React SPA (served by Vite on port 5173).
- They select a platform tab (YouTube / Facebook / Instagram).
- They set a **Target URL** via the ⚙️ settings modal (e.g., a YouTube channel URL or a public Instagram post URL).
- For YouTube: they provide a **YouTube Data API v3 key** in the input field.
- For Facebook/Instagram: the **Apify API Token** is either pasted into the input field OR read automatically from the `APIFY_API_TOKEN` environment variable / Codespaces Secret.
- React packages this into a JSON body and sends `POST /api/analyze` to the FastAPI backend.

### **Step 2: Non-Blocking Dispatch (FastAPI + Celery)**
- FastAPI receives the request at the `trigger_analysis` route.
- **Critical Step:** Instead of running the analysis synchronously (which could take 60+ seconds), FastAPI calls `run_sentiment_agent.delay(...)` — this pushes the job onto a **Celery task queue** backed by a local SQLite broker.
- FastAPI immediately responds with `{"job_id": "..."}`. The browser is **never blocked**.
- React starts polling `GET /api/task-status/{job_id}` every 3 seconds and displays the live status message in the UI (e.g., *"Scraping via Apify... this may take 30–60 seconds"*).

### **Step 3: Data Acquisition (FetcherAgent)**
The Celery worker executes `run_sentiment_agent`. Inside, the `FetcherAgent` runs differently per platform:

**YouTube path:**
- Parses the target as a video URL, bare video ID, `@handle`, or `UCxxxx` channel ID using regex.
- Resolves channels to their uploads playlist via the YouTube Data API.
- Uses a `ThreadPoolExecutor` (8 workers) to fetch comments from up to 50 videos concurrently.

**Facebook / Instagram path:**
- Calls `agents/apify_fetcher.py` → `fetch_meta_comments(url, platform, apify_token)`.
- Invokes either `apify/instagram-comment-scraper` or `apify/facebook-comments-scraper` via the `ApifyClient`.
- Waits for the Apify cloud actor to complete (typically 20–60 seconds).
- Iterates the actor's output dataset, normalizing every item to the **InternalCommentSchema**: `{platform, source_id, parent_post_id, author, text, timestamp}`.

### **Step 4: AI Analysis (PreprocessorAgent + SentimentAnalyzerAgent)**
- The raw comment list is passed to `PreprocessorAgent`, which strips URLs and whitespace noise via regex.
- Clean text is passed to the `SentimentAnalyzerAgent`, which runs **HuggingFace DistilBERT** (`distilbert-base-uncased-finetuned-sst-2-english`) locally.
- DistilBERT returns a `POSITIVE` or `NEGATIVE` label plus a confidence score (0.0–1.0) for each comment — all inference runs **on-device with no external API call**.

### **Step 5: Database Storage (SQLAlchemy + SQLite)**
- The Celery task iterates the processed comments.
- For each comment, it checks `source_id` to prevent duplicates, then writes a new `SentimentResult` row to `sql_app.db`.
- The task marks itself `SUCCESS` with `{"status": "success", "processed_reviews": N}`.

### **Step 6: Visualization (React + Recharts)**
- The React polling loop sees `done: true` from `/api/task-status`.
- It immediately fires `GET /api/dashboard/{platform}`.
- The `VisualizerAgent` queries SQLite, computes aggregated stats (counts, percentages, timeline breakdown), and returns a structured JSON response.
- Recharts renders the **Sentiment Distribution Pie Chart** and **Sentiment Timeline Line Chart** in real-time.

---

## 👨‍🏫 2. Expected Examiner Questions & Answers

### **Q1. Why did you choose FastAPI over Flask or Django?**
> *"FastAPI was the correct choice for two specific reasons. First, it natively supports async programming and background task offloading — essential because fetching from YouTube or triggering an Apify scraping run can take 60+ seconds, which would cause a standard Flask thread to block and the browser to timeout. Second, FastAPI auto-generates OpenAPI documentation at `/docs`, which accelerated development significantly. We further improved scalability by pairing it with a Celery worker, so the API and the AI pipeline run in completely separate processes."*

### **Q2. What is Apify and why did you use it instead of the official Meta Graph API?**
> *"The official Meta Graph API requires a Business Verification process that takes approximately 2 weeks and requires a live production app. For a college project prototype, this is impractical. Apify is a cloud web-scraping platform that provides pre-built 'Actors' — cloud functions that can scrape any public social media post on demand. Our `apify_fetcher.py` module calls `apify/instagram-comment-scraper` with a post URL and receives a normalized JSON dataset of comments within 30–60 seconds. This gives us real, live data for the demo without requiring any business-level API approval."*

### **Q3. Why did you choose DistilBERT over NLTK VADER for sentiment analysis?**
> *"VADER is a rule-based lexicon tuned for social media — fast but shallow. It cannot understand sentence context (e.g., 'not bad' vs 'bad'). DistilBERT is a Transformer model fine-tuned on a real-world human sentiment dataset (Stanford SST-2). It understands grammar and context, achieving ~91% accuracy on benchmark datasets versus ~60–70% for VADER on complex sentences. Since DistilBERT runs locally on CPU via PyTorch, it adds no latency cost from external API calls and still processes comments in a few milliseconds each."*

### **Q4. How does the token priority system work for Facebook and Instagram?**
> *"We implemented a two-level fallback in `apify_fetcher.py`. When `fetch_meta_comments()` is called, it first checks if the user pasted a token directly into the API Token field in the UI — this is passed as the `apify_token` argument. If that field is empty, it falls back to the `APIFY_API_TOKEN` environment variable, which is loaded from the `.env` file locally or from a GitHub Codespaces Secret in the cloud. This design means the app works out-of-the-box in Codespaces without any manual file editing — you just set the secret once in GitHub settings."*

### **Q5. How does the asynchronous pipeline prevent the browser from freezing?**
> *"The flow has three separate processes running simultaneously. Process 1 is the Uvicorn/FastAPI server — it only ever handles HTTP requests and always responds in milliseconds. When `POST /api/analyze` arrives, it calls `run_sentiment_agent.delay()` which queues the job and returns a `job_id` instantly. Process 2 is the Celery worker — this is where the actual Apify scraping and DistilBERT inference run; it is completely independent of the HTTP server. Process 3 is the React frontend — it polls `GET /api/task-status/{job_id}` every 3 seconds and displays the live status message until `done: true` is received. At no point does any process block another."*

### **Q6. How did you handle duplicate comments to avoid re-processing the same data?**
> *"Every comment stored in the `SentimentResult` table has a `source_id` column — for YouTube this is the YouTube Comment ID, for Apify scraped data this is the unique comment ID returned by the actor. Before inserting a new row, `tasks.py` runs a `db.query(SentimentResult).filter_by(source_id=src_id).first()` check. If the row already exists, it is skipped. This means you can re-run the pipeline on the same account multiple times — only genuinely new comments are ever processed, which saves both Apify compute credits and DistilBERT inference time."*

### **Q7. Can this application scale beyond a local machine?**
> *"Yes, and the architecture was designed with that in mind. Three specific swaps enable production scaling: (1) Replace `sql_app.db` connection string with a PostgreSQL URL — SQLAlchemy's ORM requires zero code changes since it abstracts the database engine. (2) Replace the local SQLite Celery broker with a Redis or RabbitMQ broker running on a cloud server — again, Celery's API is identical. (3) The Apify actors are already cloud-hosted, so the scraping layer scales automatically. The DistilBERT model could also be offloaded to a HuggingFace Inference Endpoint or a GPU cloud instance for faster throughput."*

### **Q8. What happens if a user provides a private Instagram post URL?**
> *"The `apify_fetcher.py` module wraps the entire Apify actor call in a try/except block. If the actor fails — either because the post is private, the URL is invalid, or the token has expired — it catches the exception, logs the error to the Uvicorn console, and raises a `ValueError` with the user-friendly message: 'Unable to fetch comments. Please ensure the post is public and the Apify token is valid.' This propagates through the Celery task as `status: error`, which the frontend displays as a red error banner instead of crashing."*
