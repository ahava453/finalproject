import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agents.fetcher import FetcherAgent

def main():
    fetcher = FetcherAgent({"facebook": "dummy_fb", "instagram": "dummy_ig"})
    
    print("Testing Facebook...")
    try:
        fetcher.fetch_comments("facebook", "12345", max_comments_per_video=5, max_videos=2)
    except Exception as e:
        print(f"Facebook error: {e}")

    print("\nTesting Instagram...")
    try:
        fetcher.fetch_comments("instagram", "67890", max_comments_per_video=5, max_videos=2)
    except Exception as e:
        print(f"Instagram error: {e}")

if __name__ == "__main__":
    main()
