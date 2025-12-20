from __future__ import annotations
from typing import Optional
from time import time


EVENT_VERSION = 1
SOURCE = "reddit"


def _to_int_epoch_seconds(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _now_epoch() -> int:
    return int(time())


def post_to_event(post: dict, ticker: str, query_meta: dict, ingested_at_utc: Optional[int] = None) -> dict:
    """
    Map a normalized post dict to a canonical event dict.
    """
    ingested = ingested_at_utc or _now_epoch()

    post_fullname = post["fullname"]  # t3_xxx
    created = _to_int_epoch_seconds(post.get("created_utc"))

    return {
        "event_version": EVENT_VERSION,
        "source": SOURCE,
        "entity_type": "post",

        "event_id": f"{SOURCE}:{post_fullname}",
        "dedup_key": f"{SOURCE}:{post_fullname}",

        "created_at_utc": created,
        "ingested_at_utc": ingested,

        "ticker": ticker,

        "subreddit": post.get("subreddit", ""),
        "permalink": post.get("permalink", ""),
        "url": post.get("url", ""),

        "post_fullname": post_fullname,
        "post_id": post.get("id", ""),

        "title": post.get("title", ""),
        "body": post.get("selftext", ""),

        "author": post.get("author", ""),
        "score": post.get("score"),

        "query_meta": query_meta,
    }


def comment_to_event(comment: dict, root_post_fullname: str, ticker: str, query_meta: dict,
                     ingested_at_utc: Optional[int] = None) -> dict:
    """
    Map a normalized comment dict to a canonical event dict.
    """
    ingested = ingested_at_utc or _now_epoch()

    comment_fullname = comment["fullname"]  # t1_xxx
    created = _to_int_epoch_seconds(comment.get("created_utc"))

    return {
        "event_version": EVENT_VERSION,
        "source": SOURCE,
        "entity_type": "comment",

        "event_id": f"{SOURCE}:{comment_fullname}",
        "dedup_key": f"{SOURCE}:{comment_fullname}",

        "created_at_utc": created,
        "ingested_at_utc": ingested,

        "ticker": ticker,

        "subreddit": query_meta.get("subreddit", ""),  # consistent, since search is by subreddit
        "permalink": "",  # optional (can be derived later if you want)
        "url": "",

        "comment_fullname": comment_fullname,
        "comment_id": comment.get("id", ""),

        "root_post_fullname": root_post_fullname,
        "parent_fullname": comment.get("parent_fullname", ""),

        "body": comment.get("body", ""),
        "author": comment.get("author", ""),
        "score": comment.get("score"),

        "query_meta": query_meta,
    }
