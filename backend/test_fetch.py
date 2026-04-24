import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agents.fetcher import FetcherAgent

def main():
    # Use account/profile-like URLs to exercise the account-path logic.
    fetcher = FetcherAgent({"facebook": "dummy_fb_token", "instagram": "dummy_ig_token"})

    print("Testing Facebook (account URL)...")
    try:
        fetcher.fetch_comments("facebook", "https://www.facebook.com/zuck", max_comments_per_video=5, max_videos=2)
    except Exception as e:
        print(f"Facebook error: {e}")

    print("\nTesting Instagram (account URL)...")
    try:
        fetcher.fetch_comments("instagram", "https://www.instagram.com/natgeo/", max_comments_per_video=5, max_videos=2)
    except Exception as e:
        print(f"Instagram error: {e}")

if __name__ == "__main__":
    main()
