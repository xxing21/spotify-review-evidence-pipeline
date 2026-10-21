# Measured 100-review pilot and offline calculator

Status: **completed**

Only saved provider usage is used here. Replay needs no API key and makes no network requests.

## Measured results

- Input rows: 100
- Completed: 100
- Quarantined: 0
- Cold wall seconds: 92.52117
- Warm wall seconds: 0.02304500000900589
- Warm new model calls: 0
- Known API subtotal (USD): 0.006916075
- Cost per 1,000 inputs (USD): 0.069160750
- Cost per completed record (USD): 0.00006916075
- Usage complete: True
- Local compute cost: unknown/unmeasured

## Per-stage measured calls

| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| enrich | 10 | 0 | 13116 | 6058 | 0.004667750 | 0 | 60.641 |
| verify | 2 | 0 | 2563 | 1209 | 0.000924725 | 0 | 12.402 |
| group | 1 | 0 | 1585 | 301 | 0.000348550 | 0 | 3.183 |
| memo | 2 | 1 | 5946 | 1147 | 0.000975050 | 0 | 14.644 |

Provider: OpenAI. Recorded usage × editable rates is a calculated API charge estimate, not an invoice reconciliation.

| Role | Model | Effort | Prompt hash | Completed review IDs |
|---|---|---|---|---:|
| enrich | gpt-6-luna | none | `ab9c554709eaee5cd29723b3da6cac136486fb9303530c0307b8f9a43f174fb1` | 100 |
| verify | gpt-6-luna | none | `12df8e97eff368c7aa6f2088d35f8e456b26e6c62cac8260d6aa4618f9e71f84` | 20 |
| group | gpt-6-luna | none | `019cf9046eee6104c99caad4a2abab58af5a7362771cfab04a8f69b3727d418e` | 0 |
| memo | gpt-6-luna | none | `7bc1100ce63aab999edf4fce853be0dd34b574cf93348b1ff89ea1161807c6e3` | 0 |

Input SHA-256: `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`.
Distinct nonempty texts: 100; cold exact-text reuse: 0; warm record cache hits: 100.
Cold throughput: 1.0808337162186774 completed records/second.
The schema version, worker/batch/output limits and complete per-call usage are saved in pilot_summary.json and pilot_calls.jsonl.

## Full-run projections — not measured runs

| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |
|---|---:|---:|---|
| base_exact_reuse | 27.0795 | 98.25 | True |
| conservative_exact_reuse | 29.7873 | 162.10 | True |
| base_no_reuse | 36.9457 | 134.04 | True |
| conservative_no_reuse | 40.6402 | 221.17 | True |

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
