# Final Year Project Report: Multi-Agent Real-Time Social Media Sentiment Analysis 

## 1. Introduction
Public opinion on social media shifts rapidly. For businesses, creators, and public figures, manually analyzing thousands of comments across different platforms to determine general sentiment is virtually impossible. This project presents a **Multi-Agent Real-Time Sentiment Analysis Platform** that automatically aggregates user comments from YouTube, Facebook, and Instagram, and runs them through an AI pipeline to provide an instant, visualized dashboard of public sentiment.

## 2. Problem Statement
To build a highly scalable, real-time analytics engine capable of fetching raw text data from disparate social network APIs, asynchronously processing the text using Natural Language Processing (NLP) techniques, and serving this data seamlessly via a modern web interface without causing blocking or timeouts.

## 3. Architecture Overview
The application follows a decoupled **Client-Server Architecture**:
*   **The Client (Frontend):** A Single Page Application (SPA) that acts as the user interface and data visualization dashboard.
*   **The Server (Backend):** An asynchronous API that orchestrates background AI agents to fetch, clean, and process data.
*   **The Database:** A local SQL store structured to eliminate duplicate processing and catalog historical analysis.

## 4. Key Modules & Multi-Agent System
The core innovation of the backend is its "AgentFlow" design, where specific tasks are delegated to modular "Agents".

1.  **FetcherAgent (Data Acquisition)**
    *   Connects to the YouTube Data API v3 and the Meta/Facebook Graph API using secure tokens.
    *   Utilizes a thread pool to concurrently blast API requests and bypass standard bottleneck limits when reading massive playlist feeds or hundreds of posts.
2.  **PreprocessorAgent (Text Analysis engine)**
    *   Receives raw payloads and strips out noise (URLs, hyper-spaces).
    *   Maintains a highly-optimized pipeline capable of scoring text locally in milliseconds.
3.  **Visualization Dashboard**
    *   Takes the database contents and processes them into aggregated data structures, feeding them into React Recharts (Pie Charts and Timeline tracking).

## 5. Technology Stack & Tools Used

### Frontend (Client-Side)
*   **React.js (via Vite):** Chosen for its rapid development environment and component-based UI rendering.
*   **Recharts:** A composable charting library built on React components for rendering the Sentiment Distribution and Sentiment Timeline graphs.
*   **Vanilla CSS:** Used for dynamic, glass-morphism themed styling and responsive layouts.
*   **Lucide-React:** Provides scalable vector icons.

### Backend (Server-Side)
*   **Python:** Chosen for its supremacy in data science and API construction.
*   **FastAPI:** A high-performance Python framework used for building the REST API. Chosen over Flask/Django for its native asynchronous capabilities and background task offloading.
*   **Uvicorn:** The lightning-fast ASGI server that runs the FastAPI application.
*   **SQLAlchemy ORM:** Used to abstract raw SQL commands and map Python classes to database tables cleanly.
*   **Requests & Google-API-Client:** Python libraries utilized by the `FetcherAgent` to handle external HTTP network traffic to social media endpoints.

### Artificial Intelligence & NLP
*   **NLTK (Natural Language Toolkit):** Used for advanced computational linguistics.
*   **VADER SentimentIntensityAnalyzer:** A lexicon and rule-based sentiment analysis tool specifically attuned to sentiments expressed in *social media*. It accurately interprets emojis, slang, acronyms, and punctuation (e.g., "GREAT!!!" vs "great"), returning a normalized sentiment score.
*   *(Experimental)* **HuggingFace PyTorch / DistilBERT:** The architecture supports swapping the VADER algorithm with local heavy-weight machine learning transformers for deeper contextual processing via `analyzer.py`.

### Database
*   **SQLite3:** A C-language library that implements a small, fast, self-contained SQL database engine. Chosen for its zero-configuration requirements, making local deployment seamless.

## 6. Execution Workflow
1.  **Initiation:** The user enters a target handle (e.g., `@handle` or a Page URL) and their respective API key on the React dashboard.
2.  **Dispatch:** FastAPI receives the POST request and pushes a job to `tasks.py` in the background, freeing up the API to immediately respond to the user, who enters a fetching queue.
3.  **Aggregation:** The `FetcherAgent` parses the handle, resolves internal IDs, pages through videos/media, and builds a massive list of scraped text.
4.  **Scoring:** The `PreprocessorAgent` sweeps through the list, using VADER NLP to label each item as Positive, Negative, or Neutral alongside an exact float score.
5.  **Storage & Retrieval:** Processed entries are committed to the SQLite `SentimentResult` table. The frontend constantly polls the `/task-status` endpoint. Upon completion, it hits `/dashboard` to safely query and render the stored results in real-time.

## 7. Conclusion
By integrating concurrent REST polling, NLP multi-agent pipelines, and asynchronous server mechanics, this platform successfully bridges the gap between raw, messy social media data and polished, immediate corporate insights. It demonstrates a robust understanding of modern full-stack engineering, API integrations, and practical Artificial Intelligence implementation.
