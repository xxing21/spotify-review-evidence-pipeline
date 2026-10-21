# Measured 500-review scaling pilot

Status: **completed**

Completed: 500/500. Cold processing: 122.152 seconds.
Known usage-based API cost: US$0.041287690. Unknown-usage calls: 8.
Unresolved reservations: US$0.04533560.
Warm replay: 0.09552966699993704 seconds; 0 new model calls.

## Actual ramp measurements

| Stage | Worker limit | Planned reviews | Seconds | Status | Completed reviews/second |
|---|---:|---:|---:|---|---:|
| enrich-1 | 1 | 40 | 22.608 | completed | 1.769 |
| enrich-2 | 2 | 60 | 14.542 | completed | 4.126 |
| enrich-4 | 4 | 80 | 13.391 | completed | 5.974 |
| enrich-8 | 8 | 320 | 47.660 | completed | 6.714 |
| verify-8 | 8 | 100 | 0.885 | failed request contract | — |
| verify-8 | 8 | 100 | 6.299 | completed | 15.876 |

## Estimated 100,000-review processing

| Scenario | Estimated API cost | Estimated hours |
|---|---:|---:|
| base_exact_reuse | US$6.612 | 3.39 |
| conservative_exact_reuse | US$6.979 | 5.53 |
| base_no_reuse | US$7.948 | 4.49 |
| conservative_no_reuse | US$8.448 | 7.36 |

## Limits and interpretation

- Estimates, not executions. Time comes from the measured eight-worker phases.
- Exact reuse assumes the full corpus distinct/nonempty ratio; actual 100k selection is not yet profiled.
- Cold is cumulative active processing: ramp stages, failed requests, corrected verification, grouping and memo. Source selection, process startup, development/repair and human/approval waiting are excluded.
- Disjoint fresh batches test ramp stages; review length/content and small sample sizes confound direct speedup comparisons.
- Conservative case includes at least 10% retries and 50% slower processing; sustained performance is unproven.
- Unknown charges remain separate. Hosting/local compute and historical paid work are excluded from projected API subtotals.
- Decisions is billed on all input tokens only; no Responses cached-input discount or output fee is applied to that endpoint.
- No provider Batch discount is assumed; requests used synchronous Standard processing.

Independent verification compares Luna Responses against GPT Decisions using the same model family. It measures consistency, not independent human accuracy.

Offline replay (no API key or model calls):

```sh
python3 -m spotify_pipeline scaling-replay
```
