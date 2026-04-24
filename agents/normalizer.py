from typing import List, Dict, Any
import re


def _as_str(v):
    if v is None:
        return ""
    return str(v)


def _detect_content_type(item: Dict[str, Any]) -> str:
    """Heuristic detection of content type: short|reel|post|video"""
    plat = (item.get("platform") or "").lower()

    # Instagram heuristics
    if plat == "instagram":
        # Actors may provide 'type', 'mediaType', or 'isReel'
        t = (item.get("type") or item.get("mediaType") or "").lower()
        if "reel" in t or item.get("isReel"):
            return "reel"
        return "post"

    # Facebook heuristics
    if plat == "facebook":
        post_url = (item.get("parent_post_id") or item.get("postUrl") or "").lower()
        if "/videos/" in post_url or "video" in (item.get("content_type") or ""):
            return "video"
        return "post"

    # YouTube heuristics (we may get a 'duration' field from videos().list)
    if plat == "youtube":
        # numeric seconds in item.get('duration_seconds')
        dur = item.get("duration_seconds")
        try:
            if dur is not None and float(dur) <= 60:
                return "short"
        except Exception:
            pass
        # fallback: check parent_post_id for '/shorts/' or other hint
        pp = (item.get("parent_post_id") or "").lower()
        if "/shorts/" in pp:
            return "short"
        return "video"

    return "post"


def normalize_comments(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a list of comments in the internal schema expected by PreprocessorAgent.

    Ensures keys: id, post_id, text, author, timestamp, platform, content_type, raw_metrics
    Also adds friendly aliases `comment_text` and `source_id` for compatibility.
    """
    out: List[Dict[str, Any]] = []

    for item in raw:
        plat = (item.get("platform") or item.get("site") or "").lower()

        cid = item.get("id") or item.get("source_id") or item.get("comment_id") or item.get("_id") or item.get("uid")
        post_id = item.get("post_id") or item.get("parent_post_id") or item.get("parent_post") or item.get("postUrl") or item.get("parentId")
        text = item.get("text") or item.get("message") or item.get("textDisplay") or item.get("original_text") or ""
        author = item.get("author") or item.get("profileName") or item.get("authorDisplayName") or item.get("ownerUsername") or "Unknown"
        timestamp = item.get("timestamp") or item.get("created_time") or item.get("publishedAt") or item.get("date") or ""

        # Provide duration_seconds if present as ISO 8601 (PT#M#S) or numeric
        duration_seconds = None
        dur = item.get("duration") or item.get("duration_iso") or item.get("duration_seconds")
        if isinstance(dur, (int, float)):
            duration_seconds = dur
        elif isinstance(dur, str) and dur:
            # parse ISO 8601 PT#M#S
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
            if m:
                h = int(m.group(1) or 0)
                mm = int(m.group(2) or 0)
                s = int(m.group(3) or 0)
                duration_seconds = h * 3600 + mm * 60 + s

        unified = {
            "platform": plat or "unknown",
            "id": _as_str(cid) if cid is not None else "",
            "post_id": _as_str(post_id) if post_id is not None else "",
            "text": _as_str(text),
            "comment_text": _as_str(text),
            "author": _as_str(author),
            "timestamp": _as_str(timestamp),
            "raw_metrics": item.get("raw_metrics", {}),
            "source": item,
        }

        if duration_seconds is not None:
            unified["duration_seconds"] = duration_seconds

        # Let heuristics decide short/reel/post/video
        unified["content_type"] = _detect_content_type({**item, **unified})

        # Backwards-compatibility aliases
        unified["source_id"] = unified["id"]
        unified["parent_post_id"] = unified["post_id"]

        out.append(unified)

    return out
