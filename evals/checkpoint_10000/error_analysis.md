# 10,000-review checkpoint: inspected limitations and recovery

All 10,000 original IDs now have validated completed records, with zero pending
or quarantined. All source inputs and earlier 100/500 cost measurements are
unchanged. The instructor checker validates every ID, row hash, cache alias,
issue membership, score, ordering and numerical claim.

The first extension stopped with 9,620 completed, 80 quarantined, 300 pending.
The 80 quarantined reviews belonged to eight batches that twice returned a
foreign/mistyped UUID. Original responses and charges are retained. A new strict
request-specific allowed-ID enum was tested offline. The user authorized one
final attempt for those 80 reviews; each used exactly three attempts and passed.
The 9,620 valid classifications were preserved, while the remaining 380 reviews
were completed. New response schemas have separate cache keys; old records retain
their original v2 provenance. All label prompts and model settings are preserved.

There were 1,034 actual checkpoint attempts, including 35 failures. Fifteen
failures returned no usage: fourteen network/timeouts and one HTTP 400. Their
US$0.049552125 reservations remain unresolved. The supplied checker reports
30 invalid_usage fields (input/output tokens for each request), so its overall
status is review_required. No token counts were invented, and no failed call was
removed to obtain a passing check. The known usage-based subtotal is
US$0.478451525; invoice reconciliation is pending. Including possible reserved
charges yields US$0.528003650 for this checkpoint. The shared ledger across all
experiments is US$0.577325415, below the US$2 limit.

Independent verification covered a seeded 2,000 source-row sample. Topic/intent/
severity differed on 397 reviews (19.85%); any field differed on 1,280 (64%).
Agreement: topic 91.9%, intent 92.95%, severity 91.25%; severity MAE 0.0935 and
sentiment MAE 0.082725. Sentiment exact agreement is 45.85%. These are comparisons
between same-model judgments, not estimates against human truth. Both routing
schema versions use the same label definitions; a shared model/rubric can share
mistakes. Quote/entity agreement is 100% by deterministic code grounding and is
not independent evidence of semantic accuracy or complete entity coverage.

2,362 needs_review records remain in business totals. A concrete Premium-control
boundary error persists in 0195d699-61d1-4fbb-a51b-508fc00c04db. Privacy-related
review 91132204-877d-4ac1-9d08-20d03f1414f6 requires severity/support inspection;
reported allegations must not become established company facts. Clear playback
failure 004d1c8a-a8c8-4746-b975-cd2f31c2a730 supports the playback alternative.
See assistant_inspection_examples.json and the final memo_review.md for inspected
examples, and verification_review.json for both answers and every disagreement.

The ranking is reproducible offline with exact means and ordering. Doubling all
rates doubles known calculated API spend; volume changes leave measurements
unchanged. Warm replay makes zero model calls. Source inputs and original pilot
measurements remain preserved. Synthetic tests stay outside business aggregates.

Measured execution is 115.82 minutes across both attempts, including restarts;
development work and approval waiting between invocations are excluded. Warm
replay takes 0.715 seconds. The full-file ingestion profile covers 660,622 rows;
only the 10,000 development reviews are classified. No full run or deployment
has started. Human golden evaluation is now complete; see evals/golden_results.md for its separate comparison and unresolved adjudication questions.
