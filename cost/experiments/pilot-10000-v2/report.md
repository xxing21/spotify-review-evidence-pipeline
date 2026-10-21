# Measured 10000-review checkpoint (incremental) and offline calculator

Status: **incomplete**

Only saved provider usage is used here. Replay needs no API key and makes no network requests.

## Measured results

- Input rows: 10000
- Completed: 9620
- Quarantined: 80
- Fresh-cache cold time: not measured; earlier results were reused
- Warm wall seconds: None
- Warm new model calls: pending
- Known API subtotal (USD): 0.360432320
- Cost per 1,000 inputs (USD): 0.036043232
- Cost per completed record (USD): 0.00003746697713097713097713097713
- Usage complete: False
- Local compute cost: unknown/unmeasured

## Per-stage measured calls

| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| enrich | 793 | 34 | 1022868 | 472771 | 0.360432320 | 14 | 5302.803 |

## Incremental checkpoint measurement

- Reused original IDs from the previous checkpoint: pending
- Newly completed original IDs: pending
- Newly classified distinct texts: pending
- Measured incremental wall seconds: 5455.981839583008
- New records per second (including verification and analysis): pending
No fresh-cache cold time is claimed. The subtotal includes only new attempted calls; inherited calls are saved separately and are not billed twice.
Enrichment projections use the newly classified text count as their denominator, rather than all saved outputs.
Verification projections use 20% of original nonempty source rows, matching this checkpoint's random sample.

Provider: OpenAI. Recorded usage × editable rates is a calculated API charge estimate, not an invoice reconciliation.

| Role | Model | Effort | Prompt hash | Completed review IDs |
|---|---|---|---|---:|
| enrich | gpt-6-luna | none | `ab9c554709eaee5cd29723b3da6cac136486fb9303530c0307b8f9a43f174fb1` | 7590 |

Input SHA-256: `pending`.
Distinct nonempty texts: pending; cold exact-text reuse: pending; warm record cache hits: pending.
Incremental throughput: pending new completed records/second.
The schema version, worker/batch/output limits and complete per-call usage are saved in pilot_summary.json and pilot_calls.jsonl.

## Full-run projections — not measured runs

| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |
|---|---:|---:|---|

These projections do not authorize a full run. The US$2 cap covers all actual calls in the local pilot ledger.

## Arithmetic and assumptions

Each item = billed units × editable USD/unit. Input, cached input, cache write and output are mutually exclusive. Reasoning is already included in output.
Incremental time includes this checkpoint's interruption/restart and analysis; prior checkpoint execution time is excluded. Warm time is separate.
Unknown charges retain ledger reservations and are excluded from the known subtotal; see calculator.json.
Standard processing; one worker; batches of ten; output cap 4096; verification fraction 20%; stronger fallback 0%.
Base projections use observed retries. Conservative projections use at least 10% retries and 50% slower stage durations.
Rates are editable in rates.csv, with official source and check date. Raw measurements remain unchanged when rates or volume change.
See pilot_summary.json for input checksum, IDs, cache counts, settings and measured throughput; pilot_calls.jsonl for every attempt.
The earlier synthetic-input model diagnostics remain under cost/; they are not repeated or included in this checkpoint's cost.

Offline command: `python -m spotify_pipeline cost replay --directory cost/checkpoint_10000`.
