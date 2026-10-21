# 10,000-review checkpoint measurement

Completed run: `pilot-10000-v3`, 10,000/10,000 records and 2,000 independent checks.
Known usage-based subtotal: US$0.478451525. Fifteen unresolved requests retain
US$0.049552125 of historical reservations. These are possible additional charges,
not reported usage or an invoice. Execution took 115.82 minutes across both
attempts; warm replay took 0.715 seconds with zero new model calls.

The instructor checker requests review only for missing usage fields. All data
and ranking checks pass. `pilot_calls.jsonl` retains all 1,034 actual checkpoint
attempts across v2/v3 exactly once. `inherited_calls.jsonl` contains earlier
100/500 call evidence, excluded from this checkpoint subtotal.

The current run extends `pilot-500-v2`; it is not a fresh-cache run.
Inherited enrichment calls are evidence only and are excluded from new spend.
All original review IDs remain present even when their text is reused.
Verification independently samples 20% of original source IDs.

The shared limit is US$2 across every actual experiment in the SQLite ledger.
The active execution limit for this user-authorized run is 180 minutes.
The earlier 100 and 500 measurements are preserved separately.

After execution, `pilot_summary.json` records measured elapsed time and cache
reuse; `pilot_calls.jsonl` records every new attempt and raw usage; `rates.csv`
contains dated editable prices; and `report.md`/`calculator.json` show arithmetic
and projections. Unknown usage retains a reservation and is not treated as free.
Local computing costs are unmeasured and separate from API usage.

Offline replay (no key or model calls):

```sh
python3 -m spotify_pipeline cost replay --directory cost/checkpoint_10000
python3 -m spotify_pipeline cost replay --directory cost/checkpoint_10000 --volume 100000
```

Projected totals are estimates only and do not authorize any larger run.
