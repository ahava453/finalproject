import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def fetch_meta_comments(
    url: str,
    platform: str,
    apify_token: Optional[str] = None,
    results_limit: int = 50,
    apify_options: Optional[Dict[str, Any]] = None,
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

    try:
        from apify_client import ApifyClient
    except Exception as e:
        raise ValueError(
            "Missing 'apify-client' package. Install with 'pip install apify-client'"
        ) from e

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

            # Merge caller-provided apify_options and environment-driven proxy/session
            extra = apify_options.copy() if isinstance(apify_options, dict) else {}

            # Environment-driven proxy/session configuration
            use_proxy = os.environ.get("APIFY_USE_PROXY", "").lower() in ("1", "true", "yes")
            proxy_groups_raw = os.environ.get("APIFY_PROXY_GROUPS", "")
            proxy_session = os.environ.get("APIFY_PROXY_SESSION", "")
            session_cookie = os.environ.get("APIFY_SESSION_COOKIE", "")
            cookies_json = os.environ.get("APIFY_COOKIES_JSON", "")

            if use_proxy:
                proxy_config = {"useApifyProxy": True}
                if proxy_groups_raw:
                    proxy_config["apifyProxyGroups"] = [g.strip() for g in proxy_groups_raw.split(",") if g.strip()]
                if proxy_session:
                    proxy_config["apifyProxySession"] = proxy_session
                # Merge with any provided proxyConfig
                if "proxyConfig" in extra and isinstance(extra["proxyConfig"], dict):
                    merged = extra["proxyConfig"].copy()
                    merged.update(proxy_config)
                    extra["proxyConfig"] = merged
                else:
                    extra["proxyConfig"] = proxy_config

            if session_cookie:
                extra.setdefault("sessionCookies", [])
                extra["sessionCookies"].append(session_cookie)
                extra["sessionCookie"] = session_cookie

            if cookies_json:
                try:
                    import json as _json

                    extra["cookies"] = _json.loads(cookies_json)
                except Exception:
                    extra["cookies"] = cookies_json

            if extra:
                run_input.update(extra)

            # Prefer posts+reels/mediaTypes when scraping an account
            if "mediaTypes" not in run_input and "mediaTypes" not in (extra or {}):
                run_input.setdefault("mediaTypes", ["post", "reel"])  # best-effort hint for actor

            logger.info(f"Apify: Calling instagram-comment-scraper for {url} (with options)")
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

            # Merge caller-provided apify_options and environment-driven proxy/session
            extra = apify_options.copy() if isinstance(apify_options, dict) else {}

            use_proxy = os.environ.get("APIFY_USE_PROXY", "").lower() in ("1", "true", "yes")
            proxy_groups_raw = os.environ.get("APIFY_PROXY_GROUPS", "")
            proxy_session = os.environ.get("APIFY_PROXY_SESSION", "")
            session_cookie = os.environ.get("APIFY_SESSION_COOKIE", "")
            cookies_json = os.environ.get("APIFY_COOKIES_JSON", "")

            if use_proxy:
                proxy_config = {"useApifyProxy": True}
                if proxy_groups_raw:
                    proxy_config["apifyProxyGroups"] = [g.strip() for g in proxy_groups_raw.split(",") if g.strip()]
                if proxy_session:
                    proxy_config["apifyProxySession"] = proxy_session
                if "proxyConfig" in extra and isinstance(extra["proxyConfig"], dict):
                    merged = extra["proxyConfig"].copy()
                    merged.update(proxy_config)
                    extra["proxyConfig"] = merged
                else:
                    extra["proxyConfig"] = proxy_config

            if session_cookie:
                extra.setdefault("sessionCookies", [])
                extra["sessionCookies"].append(session_cookie)
                extra["sessionCookie"] = session_cookie

            if cookies_json:
                try:
                    import json as _json

                    extra["cookies"] = _json.loads(cookies_json)
                except Exception:
                    extra["cookies"] = cookies_json

            if extra:
                run_input.update(extra)

            logger.info(f"Apify: Calling facebook-comments-scraper for {url} (with options)")
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
        # Surface the original error message to help debugging (token, network, actor errors)
        raise ValueError(
            f"Unable to fetch comments: {e}. "
            "Please ensure the post is public and the Apify token is valid."
        )

    logger.info(f"Apify: Scraped {len(comments)} comments from {platform}.")
    return comments
