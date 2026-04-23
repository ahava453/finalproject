# Final Year Project Report: Multi-Agent Real-Time Social Media Sentiment Analysis

## 1. Introduction
Public opinion on social media shifts rapidly. For businesses, creators, and public figures, manually analyzing thousands of comments across different platforms is virtually impossible. This project presents a **Multi-Agent Real-Time Sentiment Analysis Platform** — *AgentFlow* — that automatically aggregates user comments from YouTube, Facebook, and Instagram, runs them through a Transformer-based AI pipeline, and delivers an instant, visualized dashboard of public sentiment.

## 2. Problem Statement
To build a scalable, real-time analytics engine capable of:
- Fetching raw text data from YouTube (via the official Data API v3) and from public Facebook/Instagram posts (via the Apify web-scraping platform).
- Asynchronously processing that text using a pre-trained DistilBERT Transformer model.
- Serving the results seamlessly via a modern React web interface with zero blocking or browser timeouts.

## 3. Architecture Overview
The application follows a decoupled **Client-Server Architecture**:
- **The Client (Frontend):** A Single Page Application (SPA) that acts as the user interface and visualization dashboard built with React + Vite.
- **The Server (Backend):** A FastAPI REST API that orchestrates background AI agents via a Celery task queue.
- **The Worker:** A Celery worker process that independently runs the fetch → preprocess → store pipeline.
- **The Database:** A local SQLite store that eliminates duplicate processing and catalogs historical results.

## 4. Key Modules & Multi-Agent System
The core innovation of the backend is its "AgentFlow" design — specific tasks are delegated to modular, composable agents.

### 4.1 FetcherAgent (Data Acquisition)
- **YouTube:** Connects to the YouTube Data API v3 using a user-provided API key. Resolves `@handle` and channel URLs to internal `UCxxxx` Channel IDs, pages through the uploads playlist, and uses a `ThreadPoolExecutor` (8 workers) to concurrently download comments from multiple videos.
- **Facebook & Instagram (via Apify):** Uses the `apify-client` Python library to invoke the `apify/instagram-comment-scraper` and `apify/facebook-comments-scraper` cloud actors. This approach bypasses the 2-week Meta Business Verification process, enabling real-time scraping of any public post URL with a single Apify API token.
- **Token Priority:** For Facebook/Instagram, the token is read from (1) the UI input field first, then (2) the `APIFY_API_TOKEN` environment variable / Codespaces Secret as a fallback.

### 4.2 PreprocessorAgent (Text Analysis)
- Receives raw comment payloads from the Fetcher.
- Strips noise: URLs, excess whitespace, and HTML entities via Regular Expressions.
- Passes clean text to the **Sentiment Analyzer**.

### 4.3 SentimentAnalyzerAgent (AI/NLP Core)
- Uses **HuggingFace DistilBERT** (`distilbert-base-uncased-finetuned-sst-2-english`), a lightweight Transformer model fine-tuned on the Stanford Sentiment Treebank.
- Runs entirely locally on CPU — no external API call required for inference.
- Returns a `POSITIVE` / `NEGATIVE` label and a float confidence score (0.0–1.0) for every comment.

### 4.4 VisualizerAgent (Reporting & BI)
- Aggregates stored `SentimentResult` rows from SQLite.
- Computes sentiment distribution, timeline breakdown by date, and a human-readable **Business Intelligence (BI) Summary** (e.g., *"80% of comments are positive. 12 negative comments require review."*).
- Feeds structured JSON to the React Recharts components (Pie Chart and Sentiment Timeline Line Chart).

## 5. Technology Stack & Tools Used

### Frontend (Client-Side)
| Tool | Purpose |
|---|---|
| **React.js (via Vite)** | SPA framework, component-based UI rendering |
| **Recharts** | Pie Chart (sentiment distribution) and Line Chart (timeline) |
| **Vanilla CSS** | Glassmorphism dark-mode theme, responsive layouts |
| **Lucide-React** | Scalable SVG icon library |

### Backend (Server-Side)
| Tool | Purpose |
|---|---|
| **Python 3.11** | Core programming language |
| **FastAPI** | High-performance async REST API framework |
| **Uvicorn** | ASGI server that runs the FastAPI application |
| **Celery** | Distributed task queue for background agent execution |
| **SQLAlchemy ORM** | Database abstraction layer — maps Python classes to SQL tables |
| **SQLite3** | Zero-config embedded SQL database (broker + result storage) |
| **python-dotenv** | Loads environment variables from `.env` for local and Codespaces deployment |

### Data Acquisition
| Tool | Purpose |
|---|---|
| **google-api-python-client** | Official YouTube Data API v3 Python client |
| **apify-client** | Python SDK for the Apify cloud platform |
| **Apify: instagram-comment-scraper** | Scrapes public Instagram post comments |
| **Apify: facebook-comments-scraper** | Scrapes public Facebook post comments |

### Artificial Intelligence & NLP
| Tool | Purpose |
|---|---|
| **HuggingFace Transformers** | Model loading and inference pipeline |
| **DistilBERT (SST-2)** | Pre-trained Transformer for binary sentiment classification |
| **PyTorch** | Deep learning backend that runs DistilBERT locally on CPU |

### Deployment & DevOps
| Tool | Purpose |
|---|---|
| **GitHub** | Version control and source code hosting |
| **GitHub Codespaces** | Cloud-based development environment |
| **Codespaces Secrets** | Secure storage for `APIFY_API_TOKEN` — replaces the `.env` file in cloud |
| **.devcontainer** | Automated environment provisioning (installs deps, generates `.env`) |

## 6. Execution Workflow
1. **Initiation:** The user selects a platform tab (YouTube / Facebook / Instagram), sets a target URL in the settings modal, enters their API key (YouTube) or Apify token (FB/IG — optional if set in `.env`), and clicks **Run Analysis Pipeline**.
2. **Dispatch:** FastAPI receives the `POST /api/analyze` request, builds the correct `api_keys` dictionary, and enqueues a `run_sentiment_agent` task on the Celery worker. It instantly returns a `job_id` to the frontend.
3. **Aggregation:** The Celery worker starts. For Facebook/Instagram, it immediately emits a *"Scraping via Apify... this may take 30–60 seconds"* status to the frontend. The `FetcherAgent` calls the correct Apify actor, waits for the cloud run to complete, and retrieves up to 50 normalized comments.
4. **Scoring:** The `PreprocessorAgent` cleans each comment. The `SentimentAnalyzerAgent` (DistilBERT) scores every comment with a sentiment label and confidence score.
5. **Storage & Retrieval:** Processed entries are committed to the SQLite `SentimentResult` table, with deduplication via `source_id`. The React frontend polls `/api/task-status/{job_id}` every 3 seconds. On completion, it fetches `/api/dashboard/{platform}` and renders the Pie Chart and Timeline.

## 7. Conclusion
By integrating the Apify web-scraping platform, a locally-hosted DistilBERT Transformer model, an asynchronous Celery task queue, and a real-time React polling dashboard, this platform successfully demonstrates an end-to-end, production-aware multi-agent AI pipeline. It bridges the gap between raw social media data and polished, actionable business intelligence — without depending on restrictive API approval processes — and showcases a robust understanding of modern full-stack engineering, cloud deployment, and practical Artificial Intelligence implementation.
