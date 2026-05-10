#!/usr/bin/env python3
"""One-shot fetch helper for testing Apify fetches.

Usage:
  backend/.venv/bin/python backend/run_fetch_one.py <url> <apify_token>

This script prints a brief summary (count + up to 5 snippets) and
never echoes the token back in output.
"""
import sys
import os
from typing import List

# Ensure repo root is on sys.path so `agents` can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def safe_snip(s: str, n: int = 120) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return (s[:n] + "...") if len(s) > n else s


def main(argv: List[str]):
    if len(argv) < 3:
        print("Usage: run_fetch_one.py <url> <apify_token>")
        return 2

    url = argv[1]
    token = argv[2]

    try:
        from agents.apify_fetcher import fetch_meta_comments
    except Exception as e:
        print("ERROR: Could not import apify fetcher:", e)
        return 1

    try:
        comments = fetch_meta_comments(url, "facebook", apify_token=token, results_limit=50)
    except Exception as e:
        # Avoid printing the token; print only the exception message
        print("ERROR:", str(e))
        return 1

    print(f"Fetched {len(comments)} comments (showing up to 5):")
    for i, c in enumerate(comments[:5]):
        text = c.get("text") or c.get("message") or ""
        author = c.get("author") or c.get("profileName") or "Unknown"
        print(f"- {i+1}. {safe_snip(text)} (author: {author})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
