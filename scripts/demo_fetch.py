#!/usr/bin/env python3
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.fetcher import FetcherAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_demo():
    api_keys = {"youtube": "", "facebook":"", "instagram":""}
    fetcher = FetcherAgent(api_keys=api_keys)
    for platform in ("youtube","instagram","facebook"):
        try:
            logger.info(f"DEMO: Fetching for platform={platform} target='demo'")
            comments = fetcher.fetch_comments(platform, "demo", max_comments_per_video=5, max_videos=5)
            logger.info(f"DEMO: Got {len(comments)} normalized comments for {platform}")
            print("-"*40)
            print(f"Sample for {platform}:")
            for c in comments[:3]:
                print(c)
            print("-"*40)
        except Exception as e:
            logger.error(f"DEMO: Failed for {platform}: {e}")

if __name__ == "__main__":
    run_demo()
