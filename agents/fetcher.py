import time
import random
import logging
import re
import urllib.parse
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def extract_youtube_video_id(url_or_id: str) -> str:
    """
    Robustly extract the 11-character YouTube video ID from:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/embed/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - A bare 11-char video ID like 'dQw4w9WgXcQ'
    """
    url = url_or_id.strip()

    # If it looks like a URL, parse it properly
    if 'youtube.com' in url or 'youtu.be' in url:
        parsed = urllib.parse.urlparse(url)

        # youtu.be/VIDEO_ID
        if parsed.hostname in ('youtu.be',):
            vid = parsed.path.lstrip('/')
            # Strip any extra path segments or query params
            vid = vid.split('/')[0].split('?')[0]
            if len(vid) == 11:
                return vid

        # youtube.com/watch?v=VIDEO_ID
        if parsed.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
            qs = urllib.parse.parse_qs(parsed.query)
            if 'v' in qs:
                return qs['v'][0]

            # youtube.com/embed/VIDEO_ID  or  /shorts/VIDEO_ID  or  /v/VIDEO_ID
            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) >= 2 and path_parts[0] in ('embed', 'shorts', 'v', 'e'):
                return path_parts[1]

    # Already a bare 11-char ID
    if re.fullmatch(r'[A-Za-z0-9_\-]{11}', url):
        return url

    # Last resort: scan for 11-char segment after v=
    match = re.search(r'[?&]v=([A-Za-z0-9_\-]{11})', url)
    if match:
        return match.group(1)

    # Return as-is and let the API give a meaningful error
    return url


class FetcherAgent:
    """
    Agent responsible for retrieving data from social media platforms.
    """
    def __init__(self, api_keys: dict):
        self.api_keys = api_keys
        self.platforms = ["youtube", "facebook", "instagram"]

    def fetch_comments(self, platform: str, target: str, max_results: int = 50) -> list:
        logger.info(f"FetcherAgent: Fetching {platform} | {target}")

        if platform not in self.platforms:
            raise ValueError(f"Platform '{platform}' not supported.")

        if platform == "youtube":
            return self._fetch_youtube(target, max_results)

        # Facebook / Instagram — mock for now
        logger.warning(f"Real fetching not yet implemented for {platform}. Using mock data.")
        return self._mock_data(platform, max_results)

    # ── YouTube ──────────────────────────────────────────────────────────
    def _fetch_youtube(self, url_or_id: str, max_results: int) -> list:
        api_key = self.api_keys.get("youtube", "").strip()
        if not api_key:
            raise ValueError("YouTube API key is missing. Please enter your API key.")

        video_id = extract_youtube_video_id(url_or_id)
        logger.info(f"YouTube Fetcher: video_id='{video_id}'")

        youtube = build('youtube', 'v3', developerKey=api_key)

        all_comments = []
        next_page_token = None

        while len(all_comments) < max_results:
            batch = min(100, max_results - len(all_comments))
            kwargs = dict(
                part="snippet",
                videoId=video_id,
                maxResults=batch,
                textFormat="plainText",
                order="relevance"
            )
            if next_page_token:
                kwargs["pageToken"] = next_page_token

            try:
                response = youtube.commentThreads().list(**kwargs).execute()
            except Exception as exc:
                logger.error(f"YouTube API error: {exc}")
                raise

            for item in response.get('items', []):
                snip = item['snippet']['topLevelComment']['snippet']
                all_comments.append({
                    "id": item['id'],
                    "post_id": video_id,
                    "text": snip.get('textDisplay', ''),
                    "author": snip.get('authorDisplayName', 'Unknown'),
                    "timestamp": snip.get('publishedAt', ''),
                    "platform": "youtube",
                    "raw_metrics": {"likes": snip.get('likeCount', 0)}
                })

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        logger.info(f"YouTube Fetcher: fetched {len(all_comments)} comments.")
        return all_comments

    # ── Mock fallback ─────────────────────────────────────────────────────
    def _mock_data(self, platform: str, count: int) -> list:
        templates = [
            "Great content, really helpful!",
            "I completely disagree with this.",
            "Love the energy here 👍",
            "First!",
            "This is exactly what I needed.",
            "Terrible, do not waste your time.",
            "Been a fan for years.",
            "Can you make a part 2?",
        ]
        data = []
        for i in range(count):
            data.append({
                "id": f"{platform}_mock_{random.randint(10000,99999)}",
                "post_id": f"{platform}_post_{random.randint(100,999)}",
                "text": random.choice(templates),
                "author": f"user_{random.randint(1,1000)}",
                "timestamp": "2024-01-01T00:00:00Z",
                "platform": platform,
                "raw_metrics": {"likes": random.randint(0, 200)}
            })
        return data
