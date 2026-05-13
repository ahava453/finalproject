import os
import logging
import re
from apify_client import ApifyClient
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_profile_url(url: str, platform: str) -> bool:
    """
    Returns True if the URL points to a profile/account page rather than
    a specific post, reel, or video.

    Instagram post/reel URLs contain /p/ or /reel/ or /tv/.
    Facebook post URLs contain /posts/, /videos/, /photo, or /permalink/.
    Everything else is treated as a profile/account URL.
    """
    url = url.strip().rstrip("/")
    if platform == "instagram":
        return not bool(re.search(r"/(p|reel|tv)/", url))
    elif platform == "facebook":
        return not bool(re.search(r"/(posts|videos|photo|permalink)", url))
    return False


def _run_actor(client: ApifyClient, actor_id: str, run_input: dict) -> List[dict]:
    """
    Runs an Apify actor synchronously and returns all dataset items.

    Compatible with apify-client v2.x:
      - actor.call() returns the finished run dict (or None on timeout)
      - Items are fetched via client.run(run_id).dataset().iterate_items()
    """
    run = client.actor(actor_id).call(run_input=run_input)

    if run is None:
        raise RuntimeError(
            f"Apify actor '{actor_id}' timed out or returned no run object."
        )

    run_id = run.get("id")
    if not run_id:
        raise RuntimeError(
            f"Apify actor '{actor_id}' run completed but returned no run ID. "
            f"Run status: {run.get('status')}"
        )

    status = run.get("status", "UNKNOWN")
    if status not in ("SUCCEEDED", "READY", "RUNNING"):
        raise RuntimeError(
            f"Apify actor '{actor_id}' finished with status '{status}'. "
            "Check your Apify token and that the target URL is public."
        )

    items = list(client.run(run_id).dataset().iterate_items())
    logger.info(f"Apify: actor '{actor_id}' run {run_id} → {len(items)} items")
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Profile → post URL discovery
# ─────────────────────────────────────────────────────────────────────────────

def _get_instagram_post_urls(client: ApifyClient, profile_url: str, max_posts: int = 12) -> List[str]:
    """
    Uses apify/instagram-scraper to get recent post/reel URLs from a profile.
    """
    username = profile_url.strip().rstrip("/").split("/")[-1].lstrip("@")
    logger.info(f"Apify: fetching recent posts for Instagram profile '@{username}'")

    run_input = {
        "usernames": [username],
        "resultsType": "posts",
        "resultsLimit": max_posts,
        "addParentData": False,
    }

    try:
        items = _run_actor(client, "apify/instagram-scraper", run_input)
    except Exception as e:
        logger.error(f"Apify: instagram-scraper failed for '@{username}': {e}")
        return []

    post_urls: List[str] = []
    for item in items:
        url = item.get("url") or ""
        shortcode = item.get("shortCode") or item.get("id") or ""
        if url and "instagram.com" in url:
            post_urls.append(url)
        elif shortcode:
            post_urls.append(f"https://www.instagram.com/p/{shortcode}/")

    logger.info(f"Apify: found {len(post_urls)} posts for @{username}")
    return post_urls


def _get_facebook_post_urls(client: ApifyClient, page_url: str, max_posts: int = 12) -> List[str]:
    """
    Uses apify/facebook-pages-scraper to get recent post URLs from a Facebook page.
    """
    logger.info(f"Apify: fetching recent posts for Facebook page '{page_url}'")

    run_input = {
        "startUrls": [{"url": page_url.strip()}],
        "maxPosts": max_posts,
        "maxPostComments": 0,
        "maxReviews": 0,
    }

    try:
        items = _run_actor(client, "apify/facebook-pages-scraper", run_input)
    except Exception as e:
        logger.error(f"Apify: facebook-pages-scraper failed: {e}")
        return []

    post_urls: List[str] = []
    for item in items:
        for post in item.get("posts", []):
            url = post.get("url") or post.get("link") or ""
            if url:
                post_urls.append(url)
            if len(post_urls) >= max_posts:
                break
        if len(post_urls) >= max_posts:
            break

    logger.info(f"Apify: found {len(post_urls)} posts for Facebook page")
    return post_urls


# ─────────────────────────────────────────────────────────────────────────────
# Per-post comment fetching
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_comments_for_post(
    client: ApifyClient,
    post_url: str,
    platform: str,
    results_limit: int,
) -> List[Dict[str, Any]]:
    """
    Fetches comments for a single post/reel/video URL.
    Returns normalized comment dicts with AgentFlow InternalCommentSchema keys.
    """
    comments: List[Dict[str, Any]] = []

    if platform == "instagram":
        run_input = {
            "directUrls": [post_url],
            "resultsLimit": results_limit,
        }
        logger.info(f"Apify: instagram-comment-scraper → {post_url}")
        items = _run_actor(client, "apify/instagram-comment-scraper", run_input)

        for item in items:
            text = (item.get("text") or item.get("comment") or "").strip()
            if not text:
                continue
            source_id = str(
                item.get("id") or
                item.get("commentId") or
                f"ig_{abs(hash(text + post_url))}"
            )
            comments.append({
                "platform": "instagram",
                "source_id": source_id,
                "parent_post_id": str(item.get("shortCode") or post_url),
                "author": (
                    item.get("ownerUsername") or
                    item.get("username") or
                    "Unknown"
                ),
                "text": text,
                "timestamp": (
                    item.get("timestamp") or
                    item.get("createdAt") or
                    ""
                ),
            })

    elif platform == "facebook":
        run_input = {
            "startUrls": [{"url": post_url}],
            "resultsLimit": results_limit,
        }
        logger.info(f"Apify: facebook-comments-scraper → {post_url}")
        items = _run_actor(client, "apify/facebook-comments-scraper", run_input)

        for item in items:
            text = (
                item.get("text") or
                item.get("message") or
                item.get("comment") or
                ""
            ).strip()
            if not text:
                continue
            source_id = str(
                item.get("id") or
                item.get("commentId") or
                f"fb_{abs(hash(text + post_url))}"
            )
            comments.append({
                "platform": "facebook",
                "source_id": source_id,
                "parent_post_id": str(
                    item.get("postUrl") or
                    item.get("url") or
                    post_url
                ),
                "author": (
                    item.get("profileName") or
                    item.get("authorName") or
                    "Unknown"
                ),
                "text": text,
                "timestamp": (
                    item.get("date") or
                    item.get("time") or
                    item.get("createdAt") or
                    ""
                ),
            })

    return comments


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

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
      - Account / profile URLs  → discovers recent posts first, then fetches
                                   comments from each post (up to max_posts).
      - Single post / reel URLs → fetches comments directly.

    Token priority:
      1. apify_token argument (from frontend UI input)
      2. APIFY_API_TOKEN environment variable / .env file

    Compatible with apify-client v2.x.
    """
    load_dotenv(override=False)

    token = (apify_token or "").strip() or os.environ.get("APIFY_API_TOKEN", "").strip()

    if not token:
        raise ValueError(
            "Apify API Token is missing. "
            "Paste it into the API Token field in the UI, "
            "or add APIFY_API_TOKEN to your .env file."
        )

    url = url.strip()

    if "facebook.com" not in url and "instagram.com" not in url:
        raise ValueError(
            "Invalid URL. Must be a public Facebook page/post URL "
            "or Instagram profile/post URL."
        )

    client = ApifyClient(token)
    all_comments: List[Dict[str, Any]] = []

    # ── Profile URL → discover posts first, then fetch comments ──────────
    if _is_profile_url(url, platform):
        logger.info(
            f"Apify: '{url}' is a profile URL — "
            f"fetching up to {max_posts} recent posts first."
        )
        if platform == "instagram":
            post_urls = _get_instagram_post_urls(client, url, max_posts=max_posts)
        else:
            post_urls = _get_facebook_post_urls(client, url, max_posts=max_posts)

        if not post_urls:
            raise ValueError(
                f"Could not find any public posts on this {platform} profile. "
                "Make sure the account is public and the URL is correct."
            )

        per_post_limit = max(5, results_limit // len(post_urls))
        for i, post_url in enumerate(post_urls, 1):
            try:
                comments = _fetch_comments_for_post(
                    client, post_url, platform, per_post_limit
                )
                all_comments.extend(comments)
                logger.info(
                    f"Apify [{i}/{len(post_urls)}]: "
                    f"{len(comments)} comments from {post_url} "
                    f"(total so far: {len(all_comments)})"
                )
            except Exception as e:
                logger.warning(f"Apify: skipping post {post_url} — {e}")
                continue

    # ── Single post / reel URL → fetch comments directly ─────────────────
    else:
        logger.info(f"Apify: '{url}' is a single post URL — fetching comments directly.")
        all_comments = _fetch_comments_for_post(client, url, platform, results_limit)

    logger.info(
        f"Apify: finished — {len(all_comments)} total comments from {platform}."
    )
    return all_comments
