# Measured 10000-review checkpoint (incremental) and offline calculator

Status: **completed**

Only saved provider usage is used here. Replay needs no API key and makes no network requests.

## Measured results

- Input rows: 10000
- Completed: 10000
- Quarantined: 0
- Fresh-cache cold time: not measured; earlier results were reused
- Warm wall seconds: 0.7148679160018219
- Warm new model calls: 0
- Known API subtotal (USD): 0.478451525
- Cost per 1,000 inputs (USD): 0.0478451525
- Cost per completed record (USD): 0.0000478451525
- Usage complete: False
- Unresolved attempts: 15; historical reservations retained (USD): 0.049552125
- Reservations are possible charges at the saved rate card, not reported usage or invoice reconciliation.
- Local compute cost: unknown/unmeasured

## Per-stage measured calls

| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| enrich | 831 | 34 | 1081872 | 495876 | 0.379357470 | 14 | 5564.735 |
| verify | 201 | 1 | 302547 | 120644 | 0.097954830 | 1 | 1189.735 |
| group | 1 | 0 | 2265 | 355 | 0.000460550 | 0 | 6.698 |
| memo | 1 | 0 | 3454 | 494 | 0.000678675 | 0 | 5.045 |

## Incremental checkpoint measurement

- Reused original IDs from the previous checkpoint: 500
- Newly completed original IDs: 9500
- New enrichment work units (text/configuration pairs): 7970
- Measured incremental wall seconds: 6949.3745771240065
- New records per second (including verification and analysis): 1.3670294923045532
No fresh-cache cold time is claimed. The subtotal includes only new attempted calls; inherited calls are saved separately and are not billed twice.
Enrichment projections use the newly classified text count as their denominator, rather than all saved outputs.
Verification projections use 20% of original nonempty source rows, matching this checkpoint's random sample.
- Recovery source: pilot-10000-v2; valid results preserved: 9620
The measured subtotal and elapsed time include both checkpoint attempts. Inherited outputs keep their original label_config; the ID-constrained response schema has a distinct cache key.
Active execution and subprocess restart are measured; development/approval waiting between invocations is excluded.

Provider: OpenAI. Recorded usage × editable rates is a calculated API charge estimate, not an invoice reconciliation.

| Role | Model | Effort | Prompt hash | Completed review IDs |
|---|---|---|---|---:|
| enrich | gpt-6-luna | none | `ab9c554709eaee5cd29723b3da6cac136486fb9303530c0307b8f9a43f174fb1` | 7970 |
| verify | gpt-6-luna | none | `12df8e97eff368c7aa6f2088d35f8e456b26e6c62cac8260d6aa4618f9e71f84` | 2000 |
| group | gpt-6-luna | none | `019cf9046eee6104c99caad4a2abab58af5a7362771cfab04a8f69b3727d418e` | 0 |
| memo | gpt-6-luna | none | `7bc1100ce63aab999edf4fce853be0dd34b574cf93348b1ff89ea1161807c6e3` | 0 |

Input SHA-256: `eaa62ca6d44d717302904a9c922e99b0b4584d174309cb45295ecbc2ba2a91b5`.
Distinct nonempty texts: 8448; cold exact-text reuse: 1551; warm record cache hits: 10000.
Incremental throughput: 1.3670294923045532 new completed records/second.
The schema version, worker/batch/output limits and complete per-call usage are saved in pilot_summary.json and pilot_calls.jsonl.

## Full-run projections — not measured runs

| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |
|---|---:|---:|---|
| base_exact_reuse | 29.5186 | 115.79 | True |
| conservative_exact_reuse | 31.3978 | 184.51 | True |
| base_no_reuse | 37.9159 | 150.01 | True |
| conservative_no_reuse | 40.2568 | 238.65 | True |

Usage is incomplete. These API projections extrapolate known reported usage only; unknown charges remain separately reserved. They are not all-inclusive cost quotes.

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
