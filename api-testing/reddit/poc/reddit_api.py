import os
import requests

REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_BASE_OAUTH = "https://oauth.reddit.com"


def get_access_token():
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    if not all([client_id, client_secret, username, password]):
        raise RuntimeError("Missing Reddit credentials")

    auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    data = {
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    headers = {"User-Agent": f"nlp-trade/0.1 by {username}"}
    res = requests.post(REDDIT_TOKEN_URL, auth=auth, data=data, headers=headers, timeout=30)
    res.raise_for_status()
    return res.json()["access_token"], headers


def _auth_headers(base_headers, token):
    return {**base_headers, "Authorization": f"bearer {token}"}


def search_posts_raw(token, base_headers, subreddit, query, limit=25, sort="new", time_filter="day"):
    headers = _auth_headers(base_headers, token)
    url = f"{REDDIT_BASE_OAUTH}/r/{subreddit}/search"
    params = {
        "q": query,
        "sort": sort,
        "limit": limit,
        "t": time_filter,
        "restrict_sr": 1,
    }
    res = requests.get(url, headers=headers, params=params, timeout=30)
    res.raise_for_status()
    return res.json()


def fetch_comments_raw(token, base_headers, post_id, sort="new"):
    headers = _auth_headers(base_headers, token)
    url = f"{REDDIT_BASE_OAUTH}/comments/{post_id}"
    res = requests.get(url, headers=headers, params={"sort": sort}, timeout=30)
    res.raise_for_status()
    return res.json()
