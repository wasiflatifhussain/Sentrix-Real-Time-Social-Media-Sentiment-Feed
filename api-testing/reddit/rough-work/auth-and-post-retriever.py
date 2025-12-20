import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime


def get_access_token():
    """Fetch an OAuth2 access token from Reddit API using script app credentials."""
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    USERNAME = os.getenv("REDDIT_USERNAME")
    PASSWORD = os.getenv("REDDIT_PASSWORD")

    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD
    }
    headers = {"User-Agent": f"nlp-trade/0.1 by {USERNAME}"}

    res = requests.post("https://www.reddit.com/api/v1/access_token",
                        auth=auth, data=data, headers=headers)
    res.raise_for_status()
    token = res.json()["access_token"]
    return token, headers


def search_posts(token, base_headers, subreddit, query, limit=10, sort="new", time="day"):
    """Search posts in a subreddit for a query and return normalized dicts."""
    headers = {**base_headers, "Authorization": f"bearer {token}"}
    search_url = f"https://oauth.reddit.com/r/{subreddit}/search"
    params = {
        "q": query,
        "sort": sort,
        "limit": limit,
        "t": time
    }

    res = requests.get(search_url, headers=headers, params=params)
    res.raise_for_status()
    data = res.json()
    return normalize_posts(data)


def normalize_posts(search_json) -> list[dict]:
    """Convert Reddit JSON into a list of plain dictionaries."""
    posts: list[dict] = []
    for child in search_json.get("data", {}).get("children", []):
        d = child.get("data", {}) or {}
        pid = d.get("id")
        if not pid:
            continue
        post = {
            "id": pid,
            "fullname": d.get("name", ""),
            "subreddit": d.get("subreddit", ""),
            "title": d.get("title", ""),
            "selftext": d.get("selftext", ""),
            "url": d.get("url", ""),
            "permalink": d.get("permalink", ""),
            "author": d.get("author"),
            "score": d.get("score"),
            "created_utc": d.get("created_utc"),
        }
        posts.append(post)
    return posts

def fetch_comments_json(token: str, base_headers: dict, post_id: str, sort: str = "new"):
    """GET /comments/{id} -> returns [post_listing, comments_listing]."""
    headers = {**base_headers, "Authorization": f"bearer {token}"}
    url = f"https://oauth.reddit.com/comments/{post_id}"
    res = requests.get(url, headers=headers, params={"sort": sort})
    res.raise_for_status()
    return res.json()

def flatten_comment_tree(comments_listing_json) -> list[dict]:
    """
    Flatten comment tree into a list of dicts.
    Skips 'more' objects (TODO: add /api/morechildren if you need 100% depth).
    """
    flat: list[dict] = []

    if not isinstance(comments_listing_json, list) or len(comments_listing_json) < 2:
        return flat

    comments_listing = comments_listing_json[1]  # index 1 holds the comment tree

    def walk(children):
        for node in children:
            kind = node.get("kind")
            data = node.get("data", {})
            if kind == "t1":  # comment
                flat.append({
                    "id": data.get("id"),
                    "author": data.get("author"),
                    "body": data.get("body") or "",
                    "score": data.get("score"),
                    "created_utc": data.get("created_utc"),
                    "parent_id": data.get("parent_id"),
                })
                replies = data.get("replies")
                if isinstance(replies, dict):
                    walk(replies.get("data", {}).get("children", []))
            # kind == "more" gets skipped here

    walk(comments_listing.get("data", {}).get("children", []))
    return flat

def save_results_to_file(results):
    """Save the Reddit search results to a dated JSON file in ./result/."""
    today = datetime.now().strftime("%Y-%m-%d")
    folder = "./result"
    os.makedirs(folder, exist_ok=True)
    filename = f"{folder}/reddit_results_{today}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {filename}")
            
def main():
    load_dotenv(".env.local")

    token, headers = get_access_token()
    print("Access token:", token)

    results = search_posts(token, headers, "stocks", 'title:TSLA OR title:$TSLA OR title:"Tesla"', limit=100, sort="new", time="day")

    for post in results:
        pid = post["id"]
        try:
            cj = fetch_comments_json(token, headers, pid, sort="new")
            post["comments"] = flatten_comment_tree(cj)
        except requests.HTTPError as e:
            print(f"{pid}: failed to fetch comments ({e})")

    for i in range(len(results)):
        p = results[i]
        print(i, "=>",p["id"], p["title"][:60], p["selftext"][:60], p["url"], f"(comments: {len(p['comments'])})")

    save_results_to_file(results)

if __name__ == "__main__":
    main()
