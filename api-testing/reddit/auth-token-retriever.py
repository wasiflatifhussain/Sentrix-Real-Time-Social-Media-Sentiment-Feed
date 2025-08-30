import requests
import os
from dotenv import load_dotenv


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
    """Search posts in a subreddit for a query."""
    headers = {**base_headers, "Authorization": f"bearer {token}"}
    search_url = f"https://oauth.reddit.com/r/{subreddit}/search"
    params = {
        "q": query,
        "sort": sort,
        "limit": limit,
        "t": time,
        "restrict_sr": "true"
    }

    res = requests.get(search_url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()


def main():
    # Load variables from .env.local
    load_dotenv(".env.local")

    # Step 1: get token
    token, headers = get_access_token()
    print("Access token:", token)

    # Step 2: search posts
    results = search_posts(token, headers, "stocks", "Tesla", limit=10, sort="new", time="day")
    print(results)


if __name__ == "__main__":
    main()
