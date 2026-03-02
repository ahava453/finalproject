# Real-Time Sentiment Analysis Platform

A full-stack web application designed to analyze sentiment across social media platforms in real-time. Built with **React (Vite)**, **FastAPI**, **SQLite**, and **HuggingFace DistilBERT**.

## 🚀 Running on GitHub Codespaces (Recommended)

This repository is fully configured for GitHub Codespaces. When you open it in a Codespace, all dependencies (Node.js, Python, PyTorch) will be automatically installed!

1. Click the green **Code** button on the GitHub repository.
2. Select the **Codespaces** tab and click **Create codespace on main**.
3. Once the Codespace opens, the `.devcontainer/setup.sh` script will automatically install all frontend and backend dependencies. Wait for the terminal to say "Setup Complete!".
4. **Start the Backend:**
   Open a terminal in the Codespace and run:
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn main:app --reload --port 8000
   ```
5. **Start the Frontend:**
   Open a **second terminal** (using the `+` icon) and run:
   ```bash
   cd frontend
   npm run dev
   ```
6. A popup will appear in the bottom right asking you to open the forwarded port `5173`. Click **Open in Browser** to view the live app!

## 💻 Running Locally

If you clone this to your local machine, follow these steps:

### Backend Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install transformers torch torchvision torchaudio
uvicorn main:app --reload --port 8000
```

### Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
