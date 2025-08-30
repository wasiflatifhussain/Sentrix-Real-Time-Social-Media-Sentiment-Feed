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
        "t": time
    }

    res = requests.get(search_url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()

def extract_post_ids(search_json):
    """
    Returns a simple list of post IDs (short ids like '1n3vpov')
    from a /search response JSON.
    """
    children = search_json.get("data", {}).get("children", [])
    ids = [item.get("data", {}).get("id") for item in children if item.get("kind") == "t3"]
    return [i for i in ids if i]


def main():
    # Load variables from .env.local
    load_dotenv(".env.local")

    # Get token
    token, headers = get_access_token()
    print("Access token:", token)

    # Search posts
    results = search_posts(token, headers, "stocks", "Tesla", limit=10, sort="new", time="hour")
    print(results)
    
    ids = extract_post_ids(results)
    print("Post IDs:", ids)


if __name__ == "__main__":
    main()
