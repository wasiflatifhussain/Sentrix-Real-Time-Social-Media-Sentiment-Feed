from typing import Any


def normalize_posts(search_json: dict) -> list[dict]:
    """
    Convert Reddit listing JSON into a list of normalized post dicts.
    """
    posts: list[dict] = []
    for child in search_json.get("data", {}).get("children", []):
        d = child.get("data", {}) or {}
        pid = d.get("id")
        fullname = d.get("name")  # e.g., "t3_abc123"
        if not pid or not fullname:
            continue

        posts.append({
            "id": pid,
            "fullname": fullname,
            "subreddit": d.get("subreddit", ""),
            "title": d.get("title", "") or "",
            "selftext": d.get("selftext", "") or "",
            "url": d.get("url", "") or "",
            "permalink": d.get("permalink", "") or "",
            "author": d.get("author") or "",
            "score": d.get("score"),
            "created_utc": d.get("created_utc"),  # epoch seconds (float sometimes)
        })
    return posts


def flatten_comment_tree(comments_listing_json: Any) -> list[dict]:
    """
    Flatten comment tree into a list of normalized comment dicts.
    Skips 'more' objects.
    """
    flat: list[dict] = []

    if not isinstance(comments_listing_json, list) or len(comments_listing_json) < 2:
        return flat

    comments_listing = comments_listing_json[1]  # index 1 holds the comment tree

    def walk(children):
        for node in children:
            kind = node.get("kind")
            data = node.get("data", {}) or {}

            if kind == "t1":  # comment
                cid = data.get("id")
                parent_fullname = data.get("parent_id")  # e.g., "t3_xxx" or "t1_xxx"
                if not cid or not parent_fullname:
                    continue

                # Reddit comment fullname is "t1_{id}"
                flat.append({
                    "id": cid,  # short id
                    "fullname": f"t1_{cid}",
                    "author": data.get("author") or "",
                    "body": data.get("body") or "",
                    "score": data.get("score"),
                    "created_utc": data.get("created_utc"),
                    "parent_fullname": parent_fullname,
                })

                replies = data.get("replies")
                if isinstance(replies, dict):
                    walk(replies.get("data", {}).get("children", []))

            # kind == "more" gets skipped here

    walk(comments_listing.get("data", {}).get("children", []))
    return flat
