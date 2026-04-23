import os
import logging
from apify_client import ApifyClient
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def fetch_meta_comments(
    url: str,
    platform: str,
    apify_token: Optional[str] = None,
    results_limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetches comments from Facebook or Instagram using Apify.

    Token priority:
      1. apify_token argument (from frontend UI input)
      2. APIFY_API_TOKEN environment variable / .env file

    Maps output to the AgentFlow InternalCommentSchema.
    """
    load_dotenv(override=False)  # load .env without overriding already-set Codespaces secrets

    # Prefer UI-supplied token, fall back to env / Codespaces secret
    token = (apify_token or "").strip() or os.environ.get("APIFY_API_TOKEN", "").strip()

    if not token:
        raise ValueError(
            "Apify API Token is missing. "
            "Either paste it into the API Token field in the UI, "
            "or add APIFY_API_TOKEN to your .env file (or Codespaces Secrets)."
        )

    client = ApifyClient(token)

    # Basic public URL check
    if "facebook.com" not in url and "instagram.com" not in url:
        raise ValueError("Invalid URL. Must be a public Facebook or Instagram post URL.")

    comments: List[Dict[str, Any]] = []

    try:
        if platform == "instagram":
            run_input = {
                "directUrls": [url],
                "resultsLimit": results_limit,
            }
            logger.info(f"Apify: Calling instagram-comment-scraper for {url}")
            run = client.actor("apify/instagram-comment-scraper").call(run_input=run_input)

            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                text = item.get("text", "").strip()
                if not text:
                    continue
                comments.append({
                    "platform": "instagram",
                    "source_id": str(item.get("id", "")),
                    "parent_post_id": str(item.get("shortCode", url)),
                    "author": item.get("ownerUsername", "Unknown"),
                    "text": text,
                    "timestamp": item.get("timestamp", ""),
                })

        elif platform == "facebook":
            run_input = {
                "startUrls": [{"url": url}],
                "resultsLimit": results_limit,
            }
            logger.info(f"Apify: Calling facebook-comments-scraper for {url}")
            run = client.actor("apify/facebook-comments-scraper").call(run_input=run_input)

            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                text = item.get("text", "").strip()
                if not text:
                    continue
                comments.append({
                    "platform": "facebook",
                    "source_id": str(item.get("id", "")),
                    "parent_post_id": str(item.get("postUrl", url)),
                    "author": item.get("profileName", "Unknown"),
                    "text": text,
                    "timestamp": item.get("date", ""),
                })

    except Exception as e:
        logger.error(f"Apify fetching failed: {e}")
        raise ValueError(
            "Unable to fetch comments. "
            "Please ensure the post is public and the Apify token is valid."
        )

    logger.info(f"Apify: Scraped {len(comments)} comments from {platform}.")
    return comments
