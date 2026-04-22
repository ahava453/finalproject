# Project Viva & End-to-End Process Guide
**Multi-Agent Real-Time Sentiment Analysis**

This document serves as your ultimate presentation guide and Viva (oral examination) preparation. It explains the entire lifecycle of data in your application and provides answers to questions an external examiner is highly likely to ask you.

---

## 🏗️ 1. Step-by-Step Flow (How it actually works)

Let's trace a piece of data from the moment the user clicks "Run Analysis" to the moment a chart appears.

### **Step 1: The User Request (Frontend)**
* The user opens the React (Vite) frontend.
* They input a target (like a YouTube channel URL or @handle) and provide an API Key.
* React packages this data into a JSON object and sends a `POST /api/analyze` request to your FastAPI backend.

### **Step 2: Non-Blocking Dispatch (FastAPI)**
* The FastAPI server receives the request.
* **Crucial Step:** Instead of running the entire analysis (which might take 2 minutes) and making the browser freeze and wait, FastAPI offloads the heavy work to a **Background Task** (`tasks.py`).
* It immediately sends a response back to React saying: *"I started the job, here is a Job ID."* 
* React places a "Loading Pipeline..." spinner on the screen and begins polling the `/api/task-status` route every 3 seconds to check if the background task is done.

### **Step 3: Data Acquisition (FetcherAgent)**
* In the background, `tasks.py` spins up the `FetcherAgent`.
* The `FetcherAgent` looks at the target. If it's an `@handle`, it uses Search APIs to translate that into an internal ID (like a YouTube `UCxxxx` channel ID).
* It finds the "Uploads Playlist" for that channel, gets a list of recent videos, and uses a **Thread Pool** (running multiple network requests concurrently) to rapidly download raw comments.
* It returns a massive raw Python list of comment text.

### **Step 4: AI Analysis (PreprocessorAgent)**
* The raw text list is passed to the `PreprocessorAgent`.
* It cleans the text (stripping URLs and weird characters using Regular Expressions).
* It passes the clean text into the **NLTK VADER engine** (Valence Aware Dictionary and sEntiment Reasoner). 
* VADER analyzes the slang, emojis, and words, and generates a normalized mathematical score between 0 and 1, labeling the comment as POSITIVE, NEGATIVE, or NEUTRAL.

### **Step 5: Database Storage (SQLAlchemy & SQLite)**
* `tasks.py` connects to the local SQLite database (`sql_app.db`).
* It iterates through the analyzed comments. It checks `comment_id` to ensure it doesn't save duplicates, then commits the fresh data to the `SentimentResult` tables.
* The background task marks its status as "Done".

### **Step 6: Visualization (React & Recharts)**
* The React frontend's 3-second poll sees that the task is "Done".
* React immediately sends a `GET /api/dashboard/{platform}` request.
* The backend queries SQLite, grabs the top 500 rows, and formats them for charts.
* React's Recharts library takes this JSON array and renders the vibrant Pie Chart and Timeline graph on the screen.

---

## 👨‍🏫 2. Expected Examiner Questions & Answers

If I was the external examiner evaluating your project, here is what I would ask to test if you actually wrote and understand the code:

### **Q1. Why did you choose FastAPI over Flask or Django for your backend?**
**Your Answer:** "FastAPI was strictly necessary because of its native support for asynchronous programming (`async/await`) and built-in **BackgroundTasks**. Since fetching social media comments can take several minutes due to rate limits, a standard Flask app would block the thread and cause the browser to timeout. FastAPI allows us to instantly return a success message to the frontend while the Multi-Agent pipeline runs concurrently in the background."

### **Q2. Your project mentions PyTorch/DistilBERT, but you use NLTK VADER in production. Why?**
**Your Answer:** "While Deep Learning models like DistilBERT provide deep contextual understanding, they are incredibly heavy, require GPUs to run efficiently, and have high latency. For social media analysis, speed is critical. VADER is a rule-based lexicon explicitly tuned for social media—it genuinely understands emojis, slang, and ALL CAPS. It can process thousands of comments in milliseconds entirely locally, making it significantly more practical for this real-time pipeline."

### **Q3. How did you handle API Rate Limits (like YouTube blocking you for downloading too many comments)?**
**Your Answer:** "The `FetcherAgent` implements strict `max_results` limits and batch paging. Additionally, to avoid single-thread bottlenecks, I implemented a `ThreadPoolExecutor` with a safe subset of workers (e.g., 8 threads). This allows the application to grab chunks of data simultaneously from different videos without triggering sudden denial-of-service flags from the platform."

### **Q4. Can this application scale to millions of users or Enterprise-sized datasets?**
**Your Answer:** "The current architecture uses SQLite, which is perfect for a self-contained local demonstration. However, because the backend is modular, scaling is straightforward:
1. Swap the local `sql_app.db` connection string for a cloud PostgreSQL instance.
2. Swap out FastAPI's local `BackgroundTasks` for a distributed Redis + Celery worker queue. 
Because the Agents are decoupled from the API layer, the scraper and AI models would function identically on a massive cloud cluster."

### **Q5. In your frontend, why are there two different 'Refresh' buttons?**
**Your Answer:** "This demonstrates a clean separation of concerns. The refresh button in the main header invokes the `handleAnalyze` function—it physically hits the external APIs (YouTube/Facebook), runs the AI models, and writes to the DB. It's an expensive operation. The smaller refresh card in the dashboard only invokes `loadDashboard` which queries the local SQLite database to retrieve and re-render the charts. This prevents us from wasting API quota if a user just wants to reload the graphs."

### **Q6. What happens if a user types a YouTube URL instead of a Channel Handle?**
**Your Answer:** "The `FetcherAgent` contains URL extraction logic (`extract_youtube_video_id`). It uses regular expressions and URL parsing to detect if the string contains `v=ID` or `youtu.be`. If it detects a single video, it limits scraping to just that video. If it doesn't see a video ID, it treats the string as a channel, looks up the channel's 'Uploads Playlist' via the YouTube API, and iterates through up to 50 recent videos."
