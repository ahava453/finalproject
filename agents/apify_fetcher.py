import os
import logging
from apify_client import ApifyClient
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def fetch_meta_comments(url: str, platform: str) -> List[Dict[str, Any]]:
    """
    Fetches comments from Facebook or Instagram using Apify.
    Maps output to InternalCommentSchema format.
    """
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        logger.warning("APIFY_API_TOKEN is not configured. Falling back to empty list.")
        raise ValueError("Apify API Token is missing. Please add APIFY_API_TOKEN to your .env file.")
        
    client = ApifyClient(token)
    
    # Very basic public URL check
    if "facebook.com" not in url and "instagram.com" not in url:
        raise ValueError("Invalid URL. Must be a Facebook or Instagram URL.")
        
    comments = []
    
    try:
        if platform == "instagram":
            # Instagram Comment Scraper
            run_input = {
                "directUrls": [url],
                "resultsLimit": 50,
            }
            logger.info(f"Apify: Calling instagram-comment-scraper for {url}")
            run = client.actor("apify/instagram-comment-scraper").call(run_input=run_input)
            
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                comments.append({
                    "platform": "instagram",
                    "source_id": item.get("id", ""),
                    "parent_post_id": str(item.get("shortCode", url)),
                    "author": item.get("ownerUsername", "Unknown"),
                    "text": item.get("text", ""),
                    "timestamp": item.get("timestamp", "")
                })
                
        elif platform == "facebook":
            # Facebook Comments Scraper
            run_input = {
                "startUrls": [{"url": url}],
                "resultsLimit": 50,
            }
            logger.info(f"Apify: Calling facebook-comments-scraper for {url}")
            run = client.actor("apify/facebook-comments-scraper").call(run_input=run_input)
            
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                comments.append({
                    "platform": "facebook",
                    "source_id": item.get("id", ""),
                    "parent_post_id": str(item.get("postUrl", url)),
                    "author": item.get("profileName", "Unknown"),
                    "text": item.get("text", ""),
                    "timestamp": item.get("date", "")
                })
                
    except Exception as e:
        logger.error(f"Apify fetching failed: {e}")
        raise ValueError("Unable to fetch comments. Please ensure the post is public.")

    return comments
