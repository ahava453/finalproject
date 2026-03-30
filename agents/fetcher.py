import time
import random
import logging
import re
import urllib.parse
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# URL / ID Helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_youtube_video_id(url_or_id: str) -> str | None:
    """
    Return an 11-char video ID if the input looks like a single video URL/ID,
    otherwise return None (so the caller can treat it as a channel).
    Supported formats:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://youtube.com/embed/VIDEO_ID
      - https://youtube.com/shorts/VIDEO_ID
      - A bare 11-char video ID like 'dQw4w9WgXcQ'
    """
    url = url_or_id.strip()

    if "youtube.com" in url or "youtu.be" in url:
        parsed = urllib.parse.urlparse(url)

        # youtu.be/VIDEO_ID
        if parsed.hostname in ("youtu.be",):
            vid = parsed.path.lstrip("/").split("/")[0].split("?")[0]
            if len(vid) == 11:
                return vid

        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            qs = urllib.parse.parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]

            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 2 and path_parts[0] in ("embed", "shorts", "v", "e"):
                return path_parts[1]

        # If YouTube URL but no video ID found → it's a channel/playlist URL
        return None

    # Bare 11-char video ID
    if re.fullmatch(r"[A-Za-z0-9_\-]{11}", url):
        return url

    # Last resort: v= param in a non-standard URL
    match = re.search(r"[?&]v=([A-Za-z0-9_\-]{11})", url)
    if match:
        return match.group(1)

    return None  # Treat as channel handle / channel ID


def _looks_like_channel(text: str) -> bool:
    """True if input is a channel handle or channel ID, not a video."""
    t = text.strip()
    # @Handle  or  UCxxxxxxxx…  or  channel name / URL without /watch?v=
    if t.startswith("@"):
        return True
    if re.fullmatch(r"UC[A-Za-z0-9_\-]{22}", t):
        return True
    if "youtube.com" in t and "/watch" not in t and "youtu.be" not in t:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# FetcherAgent
# ─────────────────────────────────────────────────────────────────────────────

class FetcherAgent:
    """
    Agent responsible for retrieving data from social media platforms.

    YouTube mode
    ─────────────
    • Single video  → pass a video URL or bare 11-char ID.
    • Entire channel → pass a channel URL, @handle, or channel ID (UCxxx…).
      The agent will:
        1. Resolve the channel to its uploads-playlist ID.
        2. Page through all videos in that playlist.
        3. Collect comments for each video.
    """

    def __init__(self, api_keys: dict):
        self.api_keys = api_keys
        self.platforms = ["youtube", "facebook", "instagram"]

    # ── Public entry point ────────────────────────────────────────────────

    def fetch_comments(
        self,
        platform: str,
        target: str,
        max_comments_per_video: int = 100,
        max_videos: int = 50,
    ) -> list:
        logger.info(f"FetcherAgent: Fetching {platform} | {target}")

        if platform not in self.platforms:
            raise ValueError(f"Platform '{platform}' not supported.")

        if platform == "youtube":
            return self._fetch_youtube(target, max_comments_per_video, max_videos)
        elif platform == "facebook":
            return self._fetch_facebook(target, max_comments_per_video, max_videos)
        elif platform == "instagram":
            return self._fetch_instagram(target, max_comments_per_video, max_videos)

        logger.warning(
            f"Real fetching not yet implemented for {platform}. Using mock data."
        )
        return self._mock_data(platform, max_comments_per_video)

    # ── YouTube ───────────────────────────────────────────────────────────

    # Workers for concurrent per-video comment fetching.
    # 8 is safe for typical YouTube Data API free-tier quota.
    _WORKERS = 8

    def _fetch_youtube(
        self, url_or_id: str, max_comments_per_video: int, max_videos: int
    ) -> list:
        api_key = self.api_keys.get("youtube", "").strip()
        if not api_key:
            raise ValueError("YouTube API key is missing.")

        youtube = build("youtube", "v3", developerKey=api_key)

        # ── Determine mode: single video vs. whole channel ────────────────
        video_id = extract_youtube_video_id(url_or_id)

        if video_id:
            # Single-video mode
            logger.info(f"YouTube Fetcher [single-video]: video_id='{video_id}'")
            return self._fetch_comments_for_video(youtube, video_id, max_comments_per_video)

        # Channel mode
        logger.info(f"YouTube Fetcher [channel mode]: resolving channel from '{url_or_id}'")
        channel_id = self._get_channel_id(youtube, url_or_id)
        logger.info(f"YouTube Fetcher: channel_id='{channel_id}'")

        video_ids = self._get_all_video_ids(youtube, channel_id, max_videos)
        total = len(video_ids)
        logger.info(
            f"YouTube Fetcher: found {total} videos — "
            f"fetching concurrently ({self._WORKERS} workers)."
        )

        all_comments: list = []
        skipped = 0
        done = 0
        api_key = self.api_keys.get("youtube", "").strip()

        def _worker(vid: str) -> list:
            """Each thread owns its own YouTube client to avoid shared-state issues."""
            yt = build("youtube", "v3", developerKey=api_key)
            return self._fetch_comments_for_video(yt, vid, max_comments_per_video)

        with ThreadPoolExecutor(max_workers=self._WORKERS) as pool:
            future_to_vid = {pool.submit(_worker, vid): vid for vid in video_ids}

            for future in as_completed(future_to_vid):
                vid = future_to_vid[future]
                done += 1
                try:
                    comments = future.result()
                    all_comments.extend(comments)
                    logger.info(
                        f"[{done}/{total}] {vid}: +{len(comments)} comments "
                        f"(running total: {len(all_comments)})"
                    )
                except HttpError as exc:
                    skipped += 1
                    reason = ""
                    try:
                        reason = (
                            exc.error_details[0].get("reason", "")
                            if exc.error_details
                            else ""
                        )
                    except Exception:
                        pass
                    if exc.resp.status in (400, 403, 404) or reason in (
                        "commentsDisabled",
                        "videoNotFound",
                        "forbidden",
                        "processingFailure",
                    ):
                        logger.warning(
                            f"[{done}/{total}] {vid}: comments disabled/unavailable — skipped."
                        )
                    else:
                        logger.error(
                            f"[{done}/{total}] {vid}: HTTP {exc.resp.status} — skipped."
                        )
                except Exception as exc:
                    skipped += 1
                    logger.error(
                        f"[{done}/{total}] {vid}: unexpected error — skipped. ({exc})"
                    )

        logger.info(
            f"YouTube Fetcher done: {len(all_comments)} comments from "
            f"{total - skipped}/{total} videos ({skipped} skipped)."
        )
        return all_comments


    # ── Channel ID resolution ─────────────────────────────────────────────

    def _get_channel_id(self, youtube, url_or_handle: str) -> str:
        """
        Resolve a channel URL, @handle, or UCxxx ID into a canonical channel ID.
        """
        t = url_or_handle.strip()

        # Already a channel ID
        if re.fullmatch(r"UC[A-Za-z0-9_\-]{22}", t):
            return t

        # Extract handle from URL  https://youtube.com/@handle  or  /c/name  or  /user/name
        handle = None
        if "youtube.com" in t:
            parsed = urllib.parse.urlparse(t)
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                raw = parts[-1]  # last path segment
                if raw.startswith("@"):
                    handle = raw
                elif parts[0] in ("@",):
                    handle = "@" + raw
                elif parts[0] in ("c", "user", "channel"):
                    if parts[0] == "channel":
                        # /channel/UCxxx → direct ID
                        return parts[1]
                    handle = parts[1]  # custom name
        elif t.startswith("@"):
            handle = t

        if handle:
            # v3 search by forHandle (works for @handles)
            try:
                resp = youtube.channels().list(
                    part="id", forHandle=handle.lstrip("@")
                ).execute()
                items = resp.get("items", [])
                if items:
                    return items[0]["id"]
            except Exception:
                pass

            # Fallback: search API
            try:
                resp = youtube.search().list(
                    part="snippet",
                    q=handle,
                    type="channel",
                    maxResults=1,
                ).execute()
                items = resp.get("items", [])
                if items:
                    return items[0]["snippet"]["channelId"]
            except Exception:
                pass

        # Last resort – custom URL name lookup
        try:
            resp = youtube.channels().list(
                part="id", forUsername=t.lstrip("@")
            ).execute()
            items = resp.get("items", [])
            if items:
                return items[0]["id"]
        except Exception:
            pass

        raise ValueError(
            f"Could not resolve YouTube channel from '{url_or_handle}'. "
            "Please provide a valid @handle, channel URL, or UCxxx channel ID."
        )

    # ── Uploads playlist → video IDs ──────────────────────────────────────

    def _get_all_video_ids(
        self, youtube, channel_id: str, max_videos: int
    ) -> list[str]:
        """
        Get up to `max_videos` video IDs from a channel's uploads playlist.
        """
        # The uploads playlist ID is just 'UU' + channel_id[2:]
        uploads_playlist_id = "UU" + channel_id[2:]  # channel_id starts with 'UC'
        video_ids: list[str] = []
        next_page_token: Any = None

        while len(video_ids) < max_videos:
            batch = min(50, max_videos - len(video_ids))
            kwargs: Dict[str, Any] = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": batch,
            }
            if next_page_token:
                kwargs["pageToken"] = next_page_token

            try:
                resp = youtube.playlistItems().list(**kwargs).execute()
            except HttpError as exc:
                logger.error(f"Playlist fetch error for {channel_id}: {exc}")
                break

            for item in resp.get("items", []):
                vid_id = item["contentDetails"]["videoId"]
                video_ids.append(vid_id)

            next_page_token = resp.get("nextPageToken")
            if not next_page_token:
                break

        return video_ids

    # ── Comments for one video ────────────────────────────────────────────

    def _fetch_comments_for_video(
        self, youtube, video_id: str, max_results: int
    ) -> list:
        """Fetch up to `max_results` top-level comments for a single video."""
        all_comments: list = []
        next_page_token: Any = None

        while len(all_comments) < max_results:
            batch = min(100, max_results - len(all_comments))
            kwargs: Dict[str, Any] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": batch,
                "textFormat": "plainText",
                "order": "relevance",
            }
            if next_page_token:
                kwargs["pageToken"] = next_page_token

            response = youtube.commentThreads().list(**kwargs).execute()

            for item in response.get("items", []):
                snip = item["snippet"]["topLevelComment"]["snippet"]
                all_comments.append(
                    {
                        "id": item["id"],
                        "post_id": video_id,
                        "text": snip.get("textDisplay", ""),
                        "author": snip.get("authorDisplayName", "Unknown"),
                        "timestamp": snip.get("publishedAt", ""),
                        "platform": "youtube",
                        "raw_metrics": {"likes": snip.get("likeCount", 0)},
                    }
                )

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return all_comments

    # ── Facebook ──────────────────────────────────────────────────────────

    def _fetch_facebook(self, target: str, max_comments: int, max_posts: int) -> list:
        """
        Fetch comments from a Facebook Page's posts.
        `target` should be the Page ID.
        """
        api_key = self.api_keys.get("facebook", "").strip()
        if not api_key:
            raise ValueError("Facebook Graph API token is missing.")

        # Clean target if it is a URL
        target = target.strip()
        if "facebook.com" in target:
            parsed = urllib.parse.urlparse(target)
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                target = path_parts[-1]

        # 1. Get recent posts
        posts_url = f"https://graph.facebook.com/v19.0/{target}/feed"
        params = {"fields": "id,message,created_time", "access_token": api_key, "limit": max_posts}
        try:
            resp = requests.get(posts_url, params=params)
            resp.raise_for_status()
            posts_data = resp.json().get("data", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Facebook posts fetch error: {e}")
            raise ValueError(f"Failed to fetch Facebook posts: {e}")

        all_comments = []
        for post in posts_data:
            post_id = post["id"]
            comments_url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
            c_params = {"fields": "id,message,from,created_time,like_count", "access_token": api_key, "limit": 100}
            
            # Paging through comments for this post
            while len(all_comments) < (max_posts * max_comments) and comments_url:
                try:
                    c_resp = requests.get(comments_url, params=c_params)
                    c_resp.raise_for_status()
                    c_data = c_resp.json()
                    
                    for item in c_data.get("data", []):
                        if len(all_comments) >= (max_posts * max_comments):
                            break
                        
                        author = item.get("from", {}).get("name", "Unknown")
                        all_comments.append({
                            "id": item["id"],
                            "post_id": post_id,
                            "text": item.get("message", ""),
                            "author": author,
                            "timestamp": item.get("created_time", ""),
                            "platform": "facebook",
                            "raw_metrics": {"likes": item.get("like_count", 0)}
                        })
                    
                    # Next page of comments
                    paging = c_data.get("paging", {})
                    comments_url = paging.get("next")
                    c_params = {} # The 'next' URL already contains all parameters
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Facebook comments fetch error for post {post_id}: {e}")
                    break

        return all_comments

    # ── Instagram ─────────────────────────────────────────────────────────

    def _fetch_instagram(self, target: str, max_comments: int, max_posts: int) -> list:
        """
        Fetch comments from an Instagram Business/Creator account's media.
        `target` should be the IG User ID.
        """
        api_key = self.api_keys.get("instagram", "").strip()
        if not api_key:
            raise ValueError("Instagram Graph API token is missing.")

        # Clean target if it is a URL or has @
        target = target.strip()
        if "instagram.com" in target:
            parsed = urllib.parse.urlparse(target)
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                target = path_parts[-1]
        target = target.lstrip("@")

        # 1. Get recent media
        media_url = f"https://graph.facebook.com/v19.0/{target}/media"
        params = {"fields": "id,caption,timestamp", "access_token": api_key, "limit": max_posts}
        try:
            resp = requests.get(media_url, params=params)
            resp.raise_for_status()
            media_data = resp.json().get("data", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Instagram media fetch error: {e}")
            raise ValueError(f"Failed to fetch Instagram media: {e}")

        all_comments = []
        for media in media_data:
            media_id = media["id"]
            comments_url = f"https://graph.facebook.com/v19.0/{media_id}/comments"
            c_params = {"fields": "id,text,from,timestamp,like_count", "access_token": api_key, "limit": 100}
            
            while len(all_comments) < (max_posts * max_comments) and comments_url:
                try:
                    c_resp = requests.get(comments_url, params=c_params)
                    c_resp.raise_for_status()
                    c_data = c_resp.json()
                    
                    for item in c_data.get("data", []):
                        if len(all_comments) >= (max_posts * max_comments):
                            break
                        
                        author = item.get("from", {}).get("username", "Unknown") if "from" in item else "Unknown"
                        all_comments.append({
                            "id": item["id"],
                            "post_id": media_id,
                            "text": item.get("text", ""),
                            "author": author,
                            "timestamp": item.get("timestamp", ""),
                            "platform": "instagram",
                            "raw_metrics": {"likes": item.get("like_count", 0)}
                        })
                    
                    paging = c_data.get("paging", {})
                    comments_url = paging.get("next")
                    c_params = {}
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Instagram comments fetch error for media {media_id}: {e}")
                    break

        return all_comments

    # ── Mock fallback ─────────────────────────────────────────────────────

    def _mock_data(self, platform: str, count: int) -> list:
        templates = [
            "I completely disagree with this.",
            "Love the energy here 👍",
            "First!",
            "This is exactly what I needed.",
            "Terrible, do not waste your time.",
            "Been a fan for years.",
            "Can you make a part 2?",
        ]
        return [
            {
                "id": f"{platform}_mock_{random.randint(10000, 99999)}",
                "post_id": f"{platform}_post_{random.randint(100, 999)}",
                "text": random.choice(templates),
                "author": f"user_{random.randint(1, 1000)}",
                "timestamp": "2024-01-01T00:00:00Z",
                "platform": platform,
                "raw_metrics": {"likes": random.randint(0, 200)},
            }
            for _ in range(count)
        ]
