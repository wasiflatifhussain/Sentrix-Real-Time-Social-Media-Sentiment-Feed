"""
seed_phase2_events.py

Publishes test IngestorEvent JSON messages into your RAW topic so you can verify:
- Normalizer: URLs -> <URL>, cashtags uppercased, whitespace cleanup, truncation
- FeatureExtractor: wordCount/charCount/urlCount/hashtags/mentions/cashtags/capsRatio/emojiCount/repeatedCharCount

Prereq:
  pip install kafka-python

Run:
  python seed_phase2_events.py

Then inspect your cleaned topic (in kafdrop / console consumer) and confirm:
  envelope.textView.textNormalized has "<URL>"
  envelope.eventFeatures has non-zero counts + extracted lists
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"

RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


def mk_event(i: int, title: str, text: str, ticker: str, entity_type="POST", source="REDDIT"):
    eid = f"reddit:t3_phase2_{i:02d}"
    return {
        "author": f"phase2_user_{i}",
        "capture": {
            "query": f"${ticker}",
            "sort": "new",
            "timeWindow": "week",
            "fetchedFrom": "r/stocks",
            "searchMode": "search",
        },
        "community": "stocks",
        "contentUrl": f"https://www.reddit.com/r/stocks/comments/phase2_{i:02d}/",
        "createdAtUtc": now_epoch() - 300,
        "dedupKey": eid,
        "entityType": entity_type,
        "eventId": eid,
        "eventVersion": 1,
        "ingestedAtUtc": now_epoch(),
        "lang": None,
        "metrics": {"likeCount": 0, "replyCount": None, "shareCount": None, "viewCount": None},
        "platform": {
            "id": f"phase2_{i:02d}",
            "platformType": None,
            "fullName": f"t3_phase2_{i:02d}",
            "permalink": f"/r/stocks/comments/phase2_{i:02d}/",
            "rawUrl": f"https://www.reddit.com/r/stocks/comments/phase2_{i:02d}/",
        },
        "source": source,
        "text": text,
        "thread": None,
        "ticker": ticker,
        "title": title,
    }


def to_headers(d: dict):
    # your consumer reads "source" and "entityType" headers in handler; this helps preserve context
    out = []
    for k, v in d.items():
        if v is None:
            continue
        out.append((k, str(v).encode("utf-8")))
    return out


def build_events():
    events = []

    # 1) URL + hashtag + mention + cashtags (lowercase to test uppercase normalization)
    events.append(mk_event(
        1,
        title="Check this out $tsla",
        text="Huge move today! https://example.com/path?x=1 #Stocks @Someone $aapl",
        ticker="TSLA"
    ))

    # 2) Multiple URLs (test urlCount) + www form
    events.append(mk_event(
        2,
        title="Links dump $MSFT",
        text="www.google.com and https://openai.com plus https://news.ycombinator.com #tech $msft",
        ticker="MSFT"
    ))

    # 3) Caps ratio test (lots of uppercase)
    events.append(mk_event(
        3,
        title="WHY IS $NVDA SO CRAZY",
        text="THIS STOCK IS FLYING. I AM SHOUTING. #NVDA $nvda @TRADER",
        ticker="NVDA"
    ))

    # 4) Emoji count test
    events.append(mk_event(
        4,
        title="Feeling good about $AAPL",
        text="AAPL to the moon 🚀🚀🚀!!! Love it 😄😄 #apple $aapl",
        ticker="AAPL"
    ))

    # 5) Repeated char run test
    events.append(mk_event(
        5,
        title="coooool $TSLA",
        text="This is soooooo goooood!!!!!! $tsla #wow",
        ticker="TSLA"
    ))

    # 6) Whitespace cleanup test (tabs, many spaces, many newlines, \r)
    events.append(mk_event(
        6,
        title="   spaced title   $TSLA\t\t",
        text="line1\r\n\r\n\r\n   line2   \n\n\n\nline3\t\t  $tsla   #messy   @User",
        ticker="TSLA"
    ))

    # 7) Empty-ish after normalization? (only spaces) -> should DROP in your Phase 1/2 check
    # (combinedText becomes blank-ish)
    events.append(mk_event(
        7,
        title="   ",
        text="   ",
        ticker="TSLA"
    ))

    # 8) Very long text to test truncation (max-len default 8000; adjust multiplier if needed)
    long_chunk = ("word " * 2500) + " https://example.com " + ("A" * 200)
    events.append(mk_event(
        8,
        title="Long text test $TSLA",
        text=long_chunk,
        ticker="TSLA"
    ))

    return events


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=10,
    )

    events = build_events()
    print(f"Publishing {len(events)} Phase-2 test events -> {RAW_TOPIC} ({BOOTSTRAP})")

    for e in events:
        key = e["eventId"]
        headers = {
            "source": e.get("source"),
            "entityType": e.get("entityType"),
        }
        md = producer.send(RAW_TOPIC, key=key, value=e, headers=to_headers(headers)).get(timeout=10)
        print(f"sent key={key} -> p={md.partition} off={md.offset}")

    producer.flush()
    producer.close()
    print("Done.")
    print("\nNext: inspect CLEANED topic messages and confirm:")
    print("- textView.textNormalized contains '<URL>' and cashtags are uppercased ($TSLA, $AAPL, ...)")
    print("- eventFeatures.urlCount/hashtagCount/mentionCount/cashTagCount populated")
    print("- eventFeatures.extractedHashtags/extractedMentions/extractedCashTags populated")
    print("- capsRatio/emojiCount/repeatedCharCount look reasonable")
    print("- event 7 should DROP (empty text)")


if __name__ == "__main__":
    main()
