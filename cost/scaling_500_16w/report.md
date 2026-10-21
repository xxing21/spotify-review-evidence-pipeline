# Measured 500-review scaling pilot

Status: **completed**

Initial source preparation plus active processing: 61.439 seconds; process startup excluded.

Completed: 500/500. Cold processing: 57.086 seconds.
Known usage-based API cost: US$0.038659410. Unknown-usage calls: 0.
Unresolved reservations: US$0.
Warm replay: 0.10395308301667683 seconds; 0 new model calls.

## Actual ramp measurements

| Stage | Worker limit | Planned reviews | Seconds | Status | Completed reviews/second |
|---|---:|---:|---:|---|---:|
| enrich-probe | 1 | 20 | 10.614 | completed | 1.884 |
| enrich-16 | 16 | 480 | 22.883 | completed | 20.976 |
| verify-8 | 8 | 100 | 6.478 | completed | 15.437 |

## Estimated 100,000-review processing

| Scenario | Estimated API cost | Estimated hours | Under two hours? |
|---|---:|---:|---|
| base_exact_reuse | US$6.475 | 1.87 | yes, estimated |
| conservative_exact_reuse | US$7.122 | 3.07 | no |
| base_no_reuse | US$7.448 | 2.15 | no |
| conservative_no_reuse | US$8.193 | 3.55 | no |

## Tested verification batching candidate

Derived projection combining separately measured stages; not a composite cold execution. Same 500-review sample, same 100 independently checked source IDs.

Ten reviews per verification request: 100 saved predictions in 3.327 seconds across ten requests. Extra usage cost: US$0.01209220.
Actual parent pilot plus additional trial cost: US$0.050751610; original cold/warm measurements above remain unchanged.

Forecast below replaces the verifier stage basis with this trial; it does not double-count the original and replacement verification. Verification remains 20% of source IDs.

| Scenario | Estimated API cost | Estimated minutes | Under two hours? |
|---|---:|---:|---|
| base_exact_reuse | US$5.931 | 102.9 | yes, estimated |
| conservative_exact_reuse | US$6.524 | 169.5 | no |
| base_no_reuse | US$6.904 | 120.1 | no |
| conservative_no_reuse | US$7.595 | 198.0 | no |

## Limits and interpretation

- Estimates, not executions. Time comes from the selected measured parallel phases.
- Exact reuse uses the offline proposed target profile: 100,000 original IDs and 78,288 distinct texts. No target model calls have been made; selection changes require a new profile.
- Cold is cumulative active processing: ramp stages, failed requests, corrected verification, grouping and memo. Source selection, process startup, development/repair and human/approval waiting are excluded.
- Disjoint fresh batches test ramp stages; review length/content and small sample sizes confound direct speedup comparisons.
- Conservative case includes at least 10% retries and 50% slower processing; sustained performance is unproven.
- Unknown charges remain separate. Hosting/local compute and historical paid work are excluded from projected API subtotals.
- Decisions is billed on all input tokens only; no Responses cached-input discount or output fee is applied to that endpoint.
- No provider Batch discount is assumed; requests used synchronous Standard processing.
- Steady-state forecast uses the slower of measured throughput, 600 requests/minute and 600000 tokens/minute. Burst credits are not extrapolated indefinitely.
- The current pipeline runs enrichment then verification sequentially; no unmeasured overlap or higher limiter capacity is assumed.

Independent verification compares Luna Responses against GPT Decisions using the same model family. It measures consistency, not independent human accuracy.

Offline replay (no API key or model calls):

```sh
python3 -m spotify_pipeline scaling-replay --directory /Users/xxr/Desktop/Agentic AI/Final Assignment - Spotify Reviews Dataset/cost/scaling_500_16w
```
