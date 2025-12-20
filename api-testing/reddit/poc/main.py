import json
import time
from dotenv import load_dotenv

from reddit_api import get_access_token, search_posts_raw, fetch_comments_raw
from reddit_parse import normalize_posts, flatten_comment_tree
from events import post_to_event, comment_to_event
from writer import write_jsonl


# ---------------- CONFIG ----------------

SUBREDDITS = ["stocks", "investing", "wallstreetbets", "options"]
TICKERS_FILE = "./tickets.json"

MAX_CALLS_PER_MIN = 100
CALL_INTERVAL = 60 / MAX_CALLS_PER_MIN  # 0.6 sec


# ----------- RATE LIMITER ---------------

_last_call_ts = 0.0

def rate_limited_call(fn, *args, **kwargs):
    global _last_call_ts
    now = time.time()
    elapsed = now - _last_call_ts
    if elapsed < CALL_INTERVAL:
        time.sleep(CALL_INTERVAL - elapsed)
    result = fn(*args, **kwargs)
    _last_call_ts = time.time()
    return result


# ---------------------------------------

def load_tickers():
    with open(TICKERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# TODO: if this stock is unfetched, fetch for 24 hours; else fetch only for last 1 hour
def main():
    load_dotenv(".env.local")
    token, base_headers = get_access_token()
    tickers = load_tickers()

    ingested_at = int(time.time())
    all_events = []

    # Global dedup for posts across queries/subreddits
    seen_posts = set()  # post_fullname (t3_xxx)

    for ticker_cfg in tickers:
        ticker = ticker_cfg["ticker"]
        queries = ticker_cfg["queries"]

        print(f"\n[START] ticker={ticker}")

        for subreddit in SUBREDDITS:
            for query in queries:
                query_meta = {
                    "ticker": ticker,
                    "subreddit": subreddit,
                    "query": query,
                    "sort": "new",
                    "t": "week"
                }

                raw = rate_limited_call(
                    search_posts_raw,
                    token,
                    base_headers,
                    subreddit,
                    query,
                    50,
                    "new",
                    "week"
                )

                posts = normalize_posts(raw)
                print(f"[SEARCH] {ticker} | r/{subreddit} | {len(posts)} posts")

                for post in posts:
                    post_fullname = post["fullname"]

                    # ---- Dedup post across ALL queries ----
                    if post_fullname in seen_posts:
                        continue
                    seen_posts.add(post_fullname)

                    # Post event
                    all_events.append(
                        post_to_event(
                            post,
                            ticker=ticker,
                            query_meta=query_meta,
                            ingested_at_utc=ingested_at
                        )
                    )

                    # ---- Fetch comments ONCE per post ----
                    try:
                        comments_raw = rate_limited_call(
                            fetch_comments_raw,
                            token,
                            base_headers,
                            post["id"],
                            "new"
                        )
                        comments = flatten_comment_tree(comments_raw)
                    except Exception as e:
                        print(f"[WARN] comments failed post_id={post['id']} ({e})")
                        comments = []

                    for c in comments:
                        all_events.append(
                            comment_to_event(
                                c,
                                root_post_fullname=post_fullname,
                                ticker=ticker,
                                query_meta=query_meta,
                                ingested_at_utc=ingested_at
                            )
                        )

        print(f"[DONE] ticker={ticker}")

    out_path = write_jsonl(
        all_events,
        out_dir="./out",
        prefix="reddit_all_tickers"
    )

    print(f"\nSaved {len(all_events)} events to {out_path}")


if __name__ == "__main__":
    main()
