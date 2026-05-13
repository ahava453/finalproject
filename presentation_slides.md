# Presentation Slide Content
## Multi-Agent Real-Time Social Media Sentiment Analysis — *AgentFlow*

---

## Slide 1: Abstract

**Title:** Abstract

Social media platforms generate millions of comments daily, making manual sentiment tracking impossible for businesses and creators. This project presents **AgentFlow** — a Multi-Agent Real-Time Sentiment Analysis Platform that automatically aggregates user comments from **YouTube, Facebook, and Instagram**, processes them through a **DistilBERT Transformer AI model**, and delivers an instant, interactive dashboard of public sentiment.

The system is built on a decoupled full-stack architecture using **React (Vite)** on the frontend and **FastAPI + Celery** on the backend, with a modular pipeline of four specialized agents: Fetcher, Preprocessor, Analyzer, and Visualizer. It eliminates dependency on restrictive API approval processes by integrating the **Apify web-scraping platform** for Meta platforms, and runs AI inference entirely **locally on CPU** — no paid third-party AI API required.

---

## Slide 2: Proposed System

**Title:** Proposed System

AgentFlow is a full-stack, multi-agent pipeline that transforms raw social media comments into actionable business intelligence.

**How it works:**
1. User selects a platform (YouTube / Facebook / Instagram) and enters a target URL or channel
2. FastAPI dispatches a background **Celery task** — the browser never blocks
3. The **FetcherAgent** retrieves comments via YouTube Data API v3 or Apify cloud scrapers
4. The **PreprocessorAgent** cleans text (strips URLs, HTML entities, whitespace)
5. The **SentimentAnalyzerAgent** (DistilBERT) scores each comment as POSITIVE / NEGATIVE with a confidence score
6. Results are stored in **SQLite** with deduplication
7. The **VisualizerAgent** aggregates data into charts; the React frontend polls and renders a live dashboard

**Key innovation:** The Celery task queue enables asynchronous, non-blocking AI processing — the frontend polls every 3 seconds and updates in real time without timeouts.

---

## Slide 3: Advantages

**Title:** Advantages

- **Cross-Platform Coverage** — Supports YouTube, Facebook, and Instagram from a single unified interface
- **No API Approval Bottleneck** — Uses Apify to bypass Meta's 2-week Business Verification process; any public post URL works instantly
- **Local AI Inference** — DistilBERT runs entirely on CPU; no paid AI API subscription needed
- **Non-Blocking Architecture** — Celery task queue ensures the browser never times out, even for large channels with hundreds of videos
- **Concurrent Fetching** — ThreadPoolExecutor with 8 workers fetches comments from multiple YouTube videos simultaneously
- **Deduplication** — SQLite `source_id` constraint prevents reprocessing the same comment twice
- **Real-Time Dashboard** — Pie chart, sentiment timeline, keyword cloud, and BI summary update automatically on task completion
- **Zero-Config Deployment** — GitHub Codespaces `.devcontainer` auto-installs all dependencies; ready to run in minutes

---

## Slide 4: System Requirements — Software

**Title:** System Requirements — Software

| Category | Requirement |
|---|---|
| **Operating System** | Windows 10/11, macOS, Linux, or GitHub Codespaces |
| **Python** | Python 3.11+ |
| **Node.js** | Node.js 18+ (for React frontend) |
| **Backend Framework** | FastAPI + Uvicorn (ASGI server) |
| **Task Queue** | Celery with SQLite as broker |
| **Database** | SQLite 3 (via SQLAlchemy ORM) |
| **AI / NLP** | HuggingFace Transformers, DistilBERT (SST-2), PyTorch |
| **Data Acquisition** | Google API Python Client (YouTube v3), Apify Client SDK |
| **Frontend** | React.js (Vite), Recharts, Lucide-React |
| **Environment** | python-dotenv, GitHub Codespaces Secrets |

---

## Slide 5: System Requirements — Hardware

**Title:** System Requirements — Hardware

| Component | Minimum | Recommended |
|---|---|---|
| **Processor** | Dual-core CPU (x86-64) | Quad-core CPU or higher |
| **RAM** | 4 GB | 8 GB (DistilBERT loads ~250 MB into memory) |
| **Storage** | 2 GB free space | 5 GB (model cache + database) |
| **GPU** | Not required | NVIDIA CUDA GPU (optional — auto-detected for faster inference) |
| **Internet** | Required | Stable broadband (for API calls and Apify scraping) |
| **Browser** | Any modern browser | Chrome / Firefox (latest) |

> DistilBERT runs on CPU by default. The system auto-detects a CUDA GPU if available and switches to it for faster inference — no configuration needed.

---

## Slide 6: Module — FetcherAgent

**Title:** Module 1 — FetcherAgent (Data Acquisition)

**Purpose:** Retrieves raw comments from social media platforms and normalizes them into a unified internal schema.

**YouTube:**
- Connects to the **YouTube Data API v3** using a user-provided API key
- Resolves `@handle`, channel URLs, and `UCxxxx` IDs to canonical channel IDs
- Pages through the uploads playlist to collect up to 50 video IDs
- Uses a **ThreadPoolExecutor (8 workers)** to concurrently fetch comments from multiple videos
- Supports both single-video and full-channel modes

**Facebook & Instagram (via Apify):**
- Invokes `apify/facebook-comments-scraper` and `apify/instagram-comment-scraper` cloud actors
- Accepts Apify token from the UI input field or falls back to the `.env` / Codespaces Secret
- Retrieves up to 50 normalized comments per public post URL

**Output:** A list of comment objects conforming to the `InternalCommentSchema` (platform, source_id, author, text, timestamp)

---

## Slide 7: Module — PreprocessorAgent

**Title:** Module 2 — PreprocessorAgent (Text Cleaning)

**Purpose:** Cleans and standardizes raw comment text before it is passed to the AI model.

**Processing Steps:**
1. **URL Removal** — Strips all `http/https` links using Regular Expressions
2. **Whitespace Normalization** — Collapses multiple spaces and trims leading/trailing whitespace
3. **HTML Entity Removal** — Decodes encoded characters (e.g., `&amp;` → `&`)
4. **Keyword Extraction** — Extracts meaningful words (length > 4, alphabetic only) for the keyword cloud

**Sentiment Pre-scoring (VADER):**
- Uses **NLTK VADER** (Valence Aware Dictionary and sEntiment Reasoner) for fast social-media-optimized pre-analysis
- Handles emoji, slang, capitalization, and punctuation natively
- Produces a compound score in `[-1, 1]`, normalized to `[0, 1]`
- Labels: `positive` (≥ 0.05), `negative` (≤ -0.05), `neutral` (between)

**Output:** Cleaned comment objects with `clean_text`, `sentiment_label`, `sentiment_score`, and `keywords`

---

## Slide 8: Module — SentimentAnalyzerAgent

**Title:** Module 3 — SentimentAnalyzerAgent (AI / NLP Core)

**Purpose:** Performs deep-learning-based binary sentiment classification on each comment.

**Model:** `distilbert-base-uncased-finetuned-sst-2-english`
- A **DistilBERT Transformer** model from HuggingFace, fine-tuned on the Stanford Sentiment Treebank (SST-2)
- 40% smaller and 60% faster than BERT, with 97% of BERT's accuracy
- Runs **entirely locally on CPU** — no external API call or internet required for inference

**Preprocessing:**
- Converts emojis to text descriptions using the `emoji` library (e.g., 🔥 → `fire`) to improve NLP accuracy on social media text

**Inference:**
- HuggingFace `pipeline("sentiment-analysis")` processes each comment
- Returns a `POSITIVE` or `NEGATIVE` label with a float confidence score (0.0 – 1.0)
- Auto-detects CUDA GPU if available; falls back to CPU seamlessly

**Output:** `{ "label": "POSITIVE", "score": 0.9987 }` per comment

---

## Slide 9: Module — VisualizerAgent

**Title:** Module 4 — VisualizerAgent (Reporting & Business Intelligence)

**Purpose:** Aggregates stored sentiment results into structured, chart-ready JSON for the React dashboard.

**Computations:**
- **Sentiment Distribution** — Counts positive / negative / neutral comments for the Pie Chart
- **Sentiment Timeline** — Groups comments by date (YYYY-MM-DD), shows last 14 days on the Line Chart
- **Platform Distribution** — Counts comments per platform for the Bar Chart
- **Top Keywords** — Finds the 10 most frequent keywords across all comments for the Keyword Cloud
- **Average Sentiment Score** — Mean confidence score across all processed comments

**Business Intelligence (BI) Summary:**
- Generates a human-readable insight string, e.g.:
  *"Sentiment across YouTube is 80% positive. The most frequently mentioned keyword is 'amazing'."*
- Flags negative spikes: *"However, 24 comments expressed negative feedback that should be reviewed."*

**Output:** Structured JSON consumed directly by React Recharts components (Pie, Line, Bar charts)

---

## Slide 10: Future Work

**Title:** Future Work

- **Additional Platforms** — Extend FetcherAgent to support Twitter/X, Reddit, TikTok, and LinkedIn using their respective APIs or Apify actors
- **Multilingual Sentiment** — Replace SST-2 DistilBERT with a multilingual model (e.g., `xlm-roberta`) to analyze comments in languages other than English
- **Aspect-Based Sentiment Analysis (ABSA)** — Identify sentiment toward specific topics within a comment (e.g., "great video, terrible audio")
- **Real-Time Webhooks** — Replace polling with WebSocket connections for instant push updates to the dashboard
- **User Authentication** — Add JWT-based login so multiple users can manage their own analysis history
- **Scheduled Analysis** — Allow users to set recurring jobs (e.g., daily channel scan) using Celery Beat
- **Export & Reporting** — Enable CSV / PDF export of sentiment reports for business use
- **Cloud Deployment** — Containerize with Docker and deploy to AWS / GCP with a managed PostgreSQL database replacing SQLite

---

## Slide 11: Conclusion

**Title:** Conclusion

AgentFlow successfully demonstrates an end-to-end, production-aware **Multi-Agent AI Pipeline** that bridges the gap between raw social media data and polished, actionable business intelligence.

**Key Achievements:**
- Built a fully functional cross-platform sentiment analysis system covering YouTube, Facebook, and Instagram
- Integrated **DistilBERT Transformer AI** running locally — no paid AI API required
- Bypassed Meta's restrictive API approval process using **Apify cloud scraping**
- Implemented a **non-blocking asynchronous architecture** with Celery, eliminating browser timeouts for large-scale analysis
- Delivered a real-time **React dashboard** with Pie Chart, Timeline, Keyword Cloud, and BI Summary
- Deployed seamlessly on **GitHub Codespaces** with zero-config environment provisioning

The project showcases a robust understanding of modern full-stack engineering, cloud deployment, and practical Artificial Intelligence — proving that scalable, real-time NLP systems can be built and deployed without enterprise-level infrastructure or budget.

---
