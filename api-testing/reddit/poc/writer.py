import json
import os
from datetime import datetime
from typing import Iterable


def write_jsonl(events: Iterable[dict], out_dir: str = "./out", prefix: str = "events"):
    """
    Writes events to a JSON Lines file (one JSON object per line).
    Returns the file path.
    """
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(out_dir, f"{prefix}_{today}.jsonl")

    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False))
            f.write("\n")

    return path
