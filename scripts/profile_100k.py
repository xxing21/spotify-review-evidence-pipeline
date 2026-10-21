"""Profile a proposed 100k source sample locally, without initializing or executing a paid run."""
import hashlib
import heapq
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import csv_rows, now, sha, write_csv, write_json


def main():
    started = time.monotonic()
    seed = "spotify-100k-planning-v1"
    selected = heapq.nsmallest(100000,
        (r for r in csv_rows("spotify_reviews_18months.csv") if r["review_text"]),
        key=lambda r: hashlib.sha256((seed+"|"+r["review_id"]).encode()).digest())
    directory = Path("cost/planning_100k")
    directory.mkdir(exist_ok=True)
    write_csv(directory/"proposed_100k_ids.csv", [{"review_id": r["review_id"]} for r in selected], ["review_id"])
    distinct = len({r["review_text"] for r in selected})
    profile = {"saved_at": now(), "scope": "Proposed 100k nonempty original source IDs for feasibility planning; no model calls, no classifications, no production run initialized",
        "selection": "100000 smallest SHA256(seed + | + original review_id), without replacement", "seed": seed,
        "source_sha256": sha("spotify_reviews_18months.csv"), "selected_nonempty_ids": len(selected),
        "distinct_nonempty_texts": distinct, "exact_text_aliases": len(selected)-distinct,
        "selected_ids_sha256": sha(directory/"proposed_100k_ids.csv"), "elapsed_seconds": time.monotonic()-started,
        "model_calls": 0, "human_labels_used": False}
    write_json(directory/"proposed_100k_profile.json", profile)
    write_json("cost/scaling_500_16w/target_profile.json", profile)
    print(f"Profiled {len(selected):,} original IDs: {distinct:,} distinct texts; zero model calls.")


if __name__ == "__main__":
    main()
