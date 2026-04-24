import time
import random
import logging
import re
import urllib.parse
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict
# NOTE: google-api-python-client is an optional runtime dependency used only
# by the YouTube fetcher. Import it lazily inside the YouTube methods so the
# module can be imported in environments where that package is not installed.

logger = logging.getLogger(__name__)

try:
    from agents.normalizer import normalize_comments
except Exception:
    # lazy import fallback in case module not present during tests
    def normalize_comments(x):
        return x

def exchange_short_lived_token(short_token: str, app_id: str, app_secret: str) -> str | None:
    """Exchanges a short-lived user token for a long-lived one (60 days)."""
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        logger.error(f"Failed to exchange token: {e}")
        return None

def resolve_instagram_id(target: str, access_token: str) -> str | None:
    """Resolves an Instagram URL or handle to an instagram_business_account ID."""
    target = target.strip().lstrip("@")
    if "instagram.com" in target:
        parsed = urllib.parse.urlparse(target)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            target = path_parts[-1]
            
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {"fields": "instagram_business_account", "access_token": access_token}
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        pages = resp.json().get("data", [])
        for page in pages:
            ig_account = page.get("instagram_business_account")
            if ig_account:
                return ig_account.get("id")
    except Exception as e:
        logger.error(f"Failed to resolve Instagram ID: {e}")
    return target # fallback


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
# Facebook / Instagram URL helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_instagram_post_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        return any(segment in path for segment in ("/p/", "/reel/", "/reels/", "/tv/", "/media"))
    except Exception:
        return False


def _is_instagram_account_url(url: str) -> bool:
    if "instagram.com" not in (url or ""):
        return False
    return not _is_instagram_post_url(url)


def _is_facebook_post_url(url: str) -> bool:
    try:
        lu = (url or "").lower()
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        return (
            "/posts/" in path
            or "/photos/" in path
            or "/videos/" in path
            or "permalink.php" in lu
            or "story_fbid=" in lu
        )
    except Exception:
        return False


def _is_facebook_account_url(url: str) -> bool:
    if "facebook.com" not in (url or ""):
        return False
    return not _is_facebook_post_url(url)


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
            raw = self._fetch_youtube(target, max_comments_per_video, max_videos)
        elif platform == "facebook":
            raw = self._fetch_facebook(target, max_comments_per_video, max_videos)
        elif platform == "instagram":
            raw = self._fetch_instagram(target, max_comments_per_video, max_videos)
        else:
            raw = self._mock_data(platform, max_comments_per_video)

        try:
            normalized = normalize_comments(raw or [])
            logger.info(f"FetcherAgent: Normalized {len(normalized)} comments for {platform}")
            return normalized
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            return raw

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

        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except Exception as e:
            raise ValueError(
                "Missing 'google-api-python-client'. Install with 'pip install google-api-python-client'"
            ) from e

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

        # Determine recent video IDs using search.list for better coverage of Shorts
        recent_video_ids = self._get_recent_video_ids(youtube, channel_id, max_videos)
        if recent_video_ids:
            video_ids = recent_video_ids

        # Fetch contentDetails to detect durations (for Shorts detection)
        durations: Dict[str, float] = {}
        def _parse_iso8601_duration(d: str) -> float:
            # Simple ISO 8601 PT#H#M#S parser
            if not d:
                return 0.0
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
            if not m:
                return 0.0
            h = int(m.group(1) or 0)
            mm = int(m.group(2) or 0)
            s = int(m.group(3) or 0)
            return float(h * 3600 + mm * 60 + s)

        try:
            # videos().list accepts up to 50 IDs per call
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i : i + 50]
                resp = youtube.videos().list(part="contentDetails", id=",".join(batch)).execute()
                for it in resp.get("items", []):
                    vid = it.get("id")
                    iso = it.get("contentDetails", {}).get("duration")
                    durations[vid] = _parse_iso8601_duration(iso)
        except Exception:
            # Non-fatal — duration detection is best-effort
            pass

        def _worker(vid: str) -> list:
            """Each thread owns its own YouTube client to avoid shared-state issues."""
            yt = build("youtube", "v3", developerKey=api_key)
            comments = self._fetch_comments_for_video(yt, vid, max_comments_per_video)
            # annotate with duration_seconds if available
            dur = durations.get(vid)
            if dur is not None:
                for c in comments:
                    try:
                        c["duration_seconds"] = dur
                    except Exception:
                        pass
            return comments

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


    def _get_recent_video_ids(self, youtube, channel_id: str, max_videos: int) -> list[str]:
        """Use search.list to find the most recent `max_videos` videos from a channel."""
        video_ids: list[str] = []
        try:
            resp = youtube.search().list(
                part="id",
                channelId=channel_id,
                order="date",
                type="video",
                maxResults=min(50, max_videos),
            ).execute()
            for item in resp.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid:
                    video_ids.append(vid)
        except Exception as exc:
            logger.error(f"YouTube search.list error: {exc}")

        # If we didn't get enough items, fallback to uploads playlist method
        if len(video_ids) < max_videos:
            more = self._get_all_video_ids(youtube, channel_id, max_videos)
            # Merge while preserving order and uniqueness
            for v in more:
                if v not in video_ids:
                    video_ids.append(v)

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
                        "source_id": item["id"],
                        "parent_post_id": video_id,
                        "text": snip.get("textDisplay", ""),
                        "author": snip.get("authorDisplayName", "Unknown"),
                        "timestamp": snip.get("publishedAt", ""),
                        "platform": "youtube"
                    }
                )

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return all_comments

    # ── Facebook ──────────────────────────────────────────────────────────

    def _fetch_facebook(self, target: str, max_comments: int, max_posts: int) -> list:
        """
        Fetch comments from a Facebook Page account URL using Apify.
        This function expects an account (page) URL, not a single post URL.
        Token must be provided via the UI `api_keys` (Apify token) — no silent fallback.
        """
        try:
            from agents.apify_fetcher import fetch_meta_comments
            apify_opts = self.api_keys.get("apify_options") if isinstance(self.api_keys.get("apify_options"), dict) else None
            ui_token = self.api_keys.get("facebook", "").strip() or None
            if not _is_facebook_account_url(target):
                raise ValueError(
                    "Facebook fetcher expects a Facebook Page account URL (not a single post URL). Example: https://www.facebook.com/nasa"
                )
            return fetch_meta_comments(target, "facebook", apify_token=ui_token, results_limit=max_posts, apify_options=apify_opts)
        except Exception as e:
            logger.error(f"Facebook Apify error: {e}")
            raise ValueError(str(e))

    # ── Instagram ─────────────────────────────────────────────────────────

    def _fetch_instagram(self, target: str, max_comments: int, max_posts: int) -> list:
        """
        Fetch comments from an Instagram profile (account) URL using Apify.
        This function expects an account/profile URL, not a single media post URL.
        Token must be provided via the UI `api_keys` (Apify token) — no silent fallback.
        """
        try:
            from agents.apify_fetcher import fetch_meta_comments
            apify_opts = self.api_keys.get("apify_options") if isinstance(self.api_keys.get("apify_options"), dict) else None
            ui_token = self.api_keys.get("instagram", "").strip() or None
            if not _is_instagram_account_url(target):
                raise ValueError(
                    "Instagram fetcher expects an Instagram account/profile URL (not a single post URL). Example: https://www.instagram.com/natgeo/"
                )
            return fetch_meta_comments(target, "instagram", apify_token=ui_token, results_limit=max_posts, apify_options=apify_opts)
        except Exception as e:
            logger.error(f"Instagram Apify error: {e}")
            raise ValueError(str(e))

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
