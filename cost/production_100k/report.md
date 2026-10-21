# Actual 100k run and offline calculator

Status: **completed**

Completed original IDs: 100,000 / 100,000; independent checks: 5,000 (5%).
Complete independent predictions: 4,998; explicit partial refusals: 2. Agreement/MAE denominators exclude partial refusals.
Distinct text classifications: 78,288; exact-text aliases: 21,712.
Active pipeline time: 55.69 minutes. Warm replay: 15.612409999972442 seconds; 0 new calls.
First paid dispatch to final response: 76.94 minutes, including interruption/manual recovery gaps; final exports and website deployment are separate.
Known API charge estimate: US$4.083881615. Unresolved reservations for this run: US$0.174263125.
Global ledger including prior work/reservations at completion: US$4.975266680 / US$10.

| Role | Attempts | Failures | Input tokens | Output tokens | Estimated API USD |
|---|---:|---:|---:|---:|---:|
| enrich | 3970 | 55 | 9110469 | 4710914 | 3.481084690 |
| verify | 502 | 4 | 6017307 | 0 | 0.60173070 |
| group | 1 | 0 | 2225 | 320 | 0.000438050 |
| memo | 1 | 0 | 3262 | 441 | 0.000628175 |

## Estimated 660,622-row execution — not a new run

| Scenario | Estimated API USD | Estimated hours |
|---|---:|---:|
| base_exact_reuse | 25.506 | 6.01 |
| conservative_exact_reuse | 27.693 | 9.78 |
| base_no_reuse | 33.350 | 7.79 |
| conservative_no_reuse | 36.203 | 12.68 |

- Estimates use actual 100k stage throughput and mutually exclusive saved usage categories.
- Grouping and memo overhead is added once. Conservative variable work includes at least 10% retries and 50% slower throughput.
- Time is bounded by measured throughput and the sustained shared request/token ceilings; burst speed is not extrapolated indefinitely.
- Full-corpus exact-text counts are known from ingestion. Other unprofiled volumes use the corpus distinct/nonempty ratio.
- Unknown usage stays visible with reservations; it is not zero. Recorded usage times editable prices is not an invoice.
- Pipeline active time excludes source preparation, manual checkpoint waiting, final export/upload and hosting work; these are not fabricated as measured zero.
- Local hardware/electricity and hosting costs are separate and unmeasured.

```sh
python3 -m spotify_pipeline production-replay
```
