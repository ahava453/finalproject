import os
import logging
import re
from apify_client import ApifyClient
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _is_profile_url(url: str, platform: str) -> bool:
    """
    Returns True if the URL points to a profile/account page rather than
    a specific post, reel, or video.

    Instagram post/reel URLs contain /p/ or /reel/.
    Facebook post URLs contain /posts/, /videos/, /photo, or a numeric post ID pattern.
    Everything else is treated as a profile/account URL.
    """
    url = url.strip().rstrip("/")
    if platform == "instagram":
        return not bool(re.search(r"/(p|reel|tv)/", url))
    elif platform == "facebook":
        return not bool(re.search(r"/(posts|videos|photo|permalink)", url))
    return False


def _get_instagram_post_urls(client: ApifyClient, profile_url: str, max_posts: int = 12) -> List[str]:
    """
    Uses the apify/instagram-scraper actor to get recent post/reel URLs
    from an Instagram profile page.
    Returns a list of post URLs (up to max_posts).
    """
    username = profile_url.strip().rstrip("/").split("/")[-1].lstrip("@")
    logger.info(f"Apify: Fetching recent posts for Instagram profile '{username}'")

    run_input = {
        "usernames": [username],
        "resultsType": "posts",
        "resultsLimit": max_posts,
        "addParentData": False,
    }

    try:
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        post_urls = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            url = item.get("url") or item.get("displayUrl") or ""
            shortcode = item.get("shortCode") or item.get("id") or ""
            if url and "instagram.com" in url:
                post_urls.append(url)
            elif shortcode:
                post_urls.append(f"https://www.instagram.com/p/{shortcode}/")
        logger.info(f"Apify: Found {len(post_urls)} posts for @{username}")
        return post_urls
    except Exception as e:
        logger.error(f"Apify: Failed to fetch Instagram posts for '{username}': {e}")
        return []


def _get_facebook_post_urls(client: ApifyClient, page_url: str, max_posts: int = 12) -> List[str]:
    """
    Uses the apify/facebook-pages-scraper actor to get recent post URLs
    from a Facebook page.
    Returns a list of post URLs (up to max_posts).
    """
    logger.info(f"Apify: Fetching recent posts for Facebook page '{page_url}'")

    run_input = {
        "startUrls": [{"url": page_url.strip()}],
        "maxPosts": max_posts,
        "maxPostComments": 0,   # we only want post URLs here, not comments
        "maxReviews": 0,
    }

    try:
        run = client.actor("apify/facebook-pages-scraper").call(run_input=run_input)
        post_urls = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            posts = item.get("posts", [])
            for post in posts:
                url = post.get("url") or post.get("link") or ""
                if url:
                    post_urls.append(url)
                if len(post_urls) >= max_posts:
                    break
            if len(post_urls) >= max_posts:
                break
        logger.info(f"Apify: Found {len(post_urls)} posts for Facebook page")
        return post_urls
    except Exception as e:
        logger.error(f"Apify: Failed to fetch Facebook posts: {e}")
        return []


def fetch_meta_comments(
    url: str,
    platform: str,
    apify_token: Optional[str] = None,
    results_limit: int = 50,
    max_posts: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetches comments from Facebook or Instagram using Apify.

    Supports both:
      - Account / profile URLs  → scrapes recent posts/reels first, then fetches
                                   comments from each post (up to max_posts).
      - Single post / reel URLs → fetches comments directly.

    Token priority:
      1. apify_token argument (from frontend UI input)
      2. APIFY_API_TOKEN environment variable / .env file

    All returned comment dicts use the AgentFlow InternalCommentSchema keys:
      platform, source_id, parent_post_id, author, text, timestamp
    """
    load_dotenv(override=False)

    token = (apify_token or "").strip() or os.environ.get("APIFY_API_TOKEN", "").strip()

    if not token:
        raise ValueError(
            "Apify API Token is missing. "
            "Either paste it into the API Token field in the UI, "
            "or add APIFY_API_TOKEN to your .env file (or Codespaces Secrets)."
        )

    url = url.strip()

    if "facebook.com" not in url and "instagram.com" not in url:
        raise ValueError(
            "Invalid URL. Must be a public Facebook page/post URL or "
            "Instagram profile/post URL."
        )

    client = ApifyClient(token)
    all_comments: List[Dict[str, Any]] = []

    # ── Determine whether this is a profile URL or a single post URL ──────
    if _is_profile_url(url, platform):
        logger.info(f"Apify: '{url}' detected as a profile/account URL — fetching posts first.")
        if platform == "instagram":
            post_urls = _get_instagram_post_urls(client, url, max_posts=max_posts)
        else:
            post_urls = _get_facebook_post_urls(client, url, max_posts=max_posts)

        if not post_urls:
            raise ValueError(
                f"Could not find any public posts on this {platform} profile. "
                "Make sure the account is public and the URL is correct."
            )

        # Fetch comments per post; distribute results_limit across posts
        per_post_limit = max(5, results_limit // len(post_urls))
        for post_url in post_urls:
            try:
                comments = _fetch_comments_for_post(
                    client, post_url, platform, per_post_limit
                )
                all_comments.extend(comments)
                logger.info(
                    f"Apify: {len(comments)} comments from {post_url} "
                    f"(running total: {len(all_comments)})"
                )
            except Exception as e:
                logger.warning(f"Apify: Skipping post {post_url} — {e}")
                continue
    else:
        # Single post / reel URL
        logger.info(f"Apify: '{url}' detected as a single post URL.")
        all_comments = _fetch_comments_for_post(client, url, platform, results_limit)

    logger.info(f"Apify: Total {len(all_comments)} comments scraped from {platform}.")
    return all_comments


def _fetch_comments_for_post(
    client: ApifyClient,
    post_url: str,
    platform: str,
    results_limit: int,
) -> List[Dict[str, Any]]:
    """
    Fetches comments for a single post/reel URL on Instagram or Facebook.
    Returns a list of normalized comment dicts.
    """
    comments: List[Dict[str, Any]] = []

    if platform == "instagram":
        run_input = {
            "directUrls": [post_url],
            "resultsLimit": results_limit,
        }
        logger.info(f"Apify: instagram-comment-scraper → {post_url}")
        run = client.actor("apify/instagram-comment-scraper").call(run_input=run_input)

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            text = (item.get("text") or item.get("comment") or "").strip()
            if not text:
                continue
            # Build a stable source_id — prefer the item's own id field
            source_id = str(
                item.get("id") or
                item.get("commentId") or
                f"ig_{hash(text + post_url)}"
            )
            comments.append({
                "platform": "instagram",
                "source_id": source_id,
                "parent_post_id": str(item.get("shortCode") or post_url),
                "author": item.get("ownerUsername") or item.get("username") or "Unknown",
                "text": text,
                "timestamp": item.get("timestamp") or item.get("createdAt") or "",
            })

    elif platform == "facebook":
        run_input = {
            "startUrls": [{"url": post_url}],
            "resultsLimit": results_limit,
        }
        logger.info(f"Apify: facebook-comments-scraper → {post_url}")
        run = client.actor("apify/facebook-comments-scraper").call(run_input=run_input)

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            text = (item.get("text") or item.get("message") or item.get("comment") or "").strip()
            if not text:
                continue
            source_id = str(
                item.get("id") or
                item.get("commentId") or
                f"fb_{hash(text + post_url)}"
            )
            comments.append({
                "platform": "facebook",
                "source_id": source_id,
                "parent_post_id": str(item.get("postUrl") or item.get("url") or post_url),
                "author": item.get("profileName") or item.get("authorName") or "Unknown",
                "text": text,
                "timestamp": item.get("date") or item.get("time") or item.get("createdAt") or "",
            })

    return comments
