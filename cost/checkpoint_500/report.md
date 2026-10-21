# Measured 500-review checkpoint (incremental) and offline calculator

Status: **completed**

Only saved provider usage is used here. Replay needs no API key and makes no network requests.

## Measured results

- Input rows: 500
- Completed: 500
- Quarantined: 0
- Fresh-cache cold time: not measured; earlier results were reused
- Warm wall seconds: 0.05025220899551641
- Warm new model calls: 0
- Known API subtotal (USD): 0.023235875
- Cost per 1,000 inputs (USD): 0.046471750
- Cost per completed record (USD): 0.00004647175
- Usage complete: True
- Local compute cost: unknown/unmeasured

## Per-stage measured calls

| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| enrich | 38 | 0 | 49353 | 22945 | 0.017638775 | 0 | 224.060 |
| verify | 10 | 0 | 13024 | 6026 | 0.004640250 | 0 | 155.926 |
| group | 1 | 0 | 1852 | 320 | 0.000391425 | 0 | 3.593 |
| memo | 1 | 0 | 3092 | 358 | 0.000565425 | 0 | 5.027 |

## Incremental checkpoint measurement

- Reused original IDs from the 100-review pilot: 100
- Newly completed original IDs: 400
- Newly classified distinct texts: 379
- Measured incremental wall seconds: 389.78172541699314
- New records per second (including verification and analysis): 1.026215376239292
No fresh-cache 500-review cold time is claimed. The subtotal includes only new attempted calls; inherited calls are saved separately and are not billed twice.
Enrichment projections use the newly classified text count as their denominator, rather than all 500 saved outputs.
Verification projections use 20% of original nonempty source rows, matching this checkpoint's random sample.

Provider: OpenAI. Recorded usage × editable rates is a calculated API charge estimate, not an invoice reconciliation.

| Role | Model | Effort | Prompt hash | Completed review IDs |
|---|---|---|---|---:|
| enrich | gpt-6-luna | none | `ab9c554709eaee5cd29723b3da6cac136486fb9303530c0307b8f9a43f174fb1` | 379 |
| verify | gpt-6-luna | none | `12df8e97eff368c7aa6f2088d35f8e456b26e6c62cac8260d6aa4618f9e71f84` | 100 |
| group | gpt-6-luna | none | `019cf9046eee6104c99caad4a2abab58af5a7362771cfab04a8f69b3727d418e` | 0 |
| memo | gpt-6-luna | none | `7bc1100ce63aab999edf4fce853be0dd34b574cf93348b1ff89ea1161807c6e3` | 0 |

Input SHA-256: `a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f`.
Distinct nonempty texts: 479; cold exact-text reuse: 21; warm record cache hits: 500.
Incremental throughput: 1.026215376239292 new completed records/second.
The schema version, worker/batch/output limits and complete per-call usage are saved in pilot_summary.json and pilot_calls.jsonl.

## Full-run projections — not measured runs

| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |
|---|---:|---:|---|
| base_exact_reuse | 28.6661 | 136.74 | True |
| conservative_exact_reuse | 31.5326 | 225.62 | True |
| base_no_reuse | 36.8767 | 165.71 | True |
| conservative_no_reuse | 40.5643 | 273.43 | True |

These projections do not authorize a full run. The US$2 cap covers all actual calls in the local pilot ledger.

## Arithmetic and assumptions

Each item = billed units × editable USD/unit. Input, cached input, cache write and output are mutually exclusive. Reasoning is already included in output.
Incremental time includes this checkpoint's interruption/restart and analysis; prior 100-review execution time is excluded. Warm time is separate.
Unknown charges retain ledger reservations and are excluded from the known subtotal; see calculator.json.
Standard processing; one worker; batches of ten; output cap 4096; verification fraction 20%; stronger fallback 0%.
Base projections use observed retries. Conservative projections use at least 10% retries and 50% slower stage durations.
Rates are editable in rates.csv, with official source and check date. Raw measurements remain unchanged when rates or volume change.
See pilot_summary.json for input checksum, IDs, cache counts, settings and measured throughput; pilot_calls.jsonl for every attempt.
The earlier synthetic-input model diagnostics remain under cost/; they are not repeated or included in this checkpoint's cost.

Offline command: `python -m spotify_pipeline cost replay --directory cost/checkpoint_500`.
