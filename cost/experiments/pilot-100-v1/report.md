# Measured 100-review pilot and offline calculator

Status: **incomplete**

Only saved provider usage is used here. Replay needs no API key and makes no network requests.

## Measured results

- Input rows: 100
- Completed: 60
- Quarantined: 40
- Cold wall seconds: None
- Warm wall seconds: None
- Warm new model calls: pending
- Known API subtotal (USD): 0.009342915
- Cost per 1,000 inputs (USD): 0.093429150
- Cost per completed record (USD): 0.00015571525
- Usage complete: False
- Local compute cost: unknown/unmeasured

## Per-stage measured calls

| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| enrich | 20 | 14 | 21039 | 12534 | 0.007900620 | 3 | 124.586 |
| verify | 3 | 2 | 3750 | 2247 | 0.001442295 | 0 | 14.571 |

## Full-run projections — not measured runs

| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |
|---|---:|---:|---|

These projections do not authorize a full run. The US$2 cap covers all actual calls in the local pilot ledger.

## Arithmetic and assumptions

Each item = billed units × editable USD/unit. Input, cached input, cache write and output are mutually exclusive. Reasoning is already included in output.
Cold time includes the recorded interruption/process restart. Warm time is incremental. Summed call time is shown separately from wall time.
Unknown charges retain ledger reservations and are excluded from the known subtotal; see calculator.json.
Standard processing; one worker; batches of ten; output cap 4096; verification fraction 20%; stronger fallback 0%.
Base projections use observed retries. Conservative projections use at least 10% retries and 50% slower stage durations.
Rates are editable in rates.csv, with official source and check date. Raw measurements remain unchanged when rates or volume change.
See pilot_summary.json for input checksum, IDs, cache counts, settings and measured throughput; pilot_calls.jsonl for every attempt.
Diagnostics, if executed, are separate in diagnostics_calls.jsonl and diagnostics.json; they share the global budget but are excluded from measured-100 projections.

Offline command: `python -m spotify_pipeline cost replay`.
