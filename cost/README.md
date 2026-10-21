# Offline calculator and explicit paid pilot

From the project root, replay saved measurements without credentials or network:

```sh
python3 -m spotify_pipeline cost replay
python3 -m spotify_pipeline cost replay --volume 100000
python3 -m spotify_pipeline cost replay --rates cost/rates.csv --budget-usd 2
```

Edit `rates.csv` to change prices, preserving USD/token units. Replay writes
`calculator.json`, `usage.csv`, and `report.md`; it never changes raw measurements.
Doubling every rate doubles the API subtotal. Changing projected volume changes
only projections. Local compute cost is unknown unless measured separately.

The only command that starts the measured pilot is:

```sh
python3 -m spotify_pipeline pilot --input cost_100.csv --execute-paid --budget-usd 2
```

Put a real OpenAI API key in local `.env`, never source code or logs. The pilot
uses the unchanged fixed 100 rows and an experiment-local result cache. It
interrupts its worker process after a saved checkpoint, resumes new IDs, and
then replays the complete pipeline warm. Repeating the same command resumes or
reuses this experiment; it does not reset paid work.

If account access fails, fix billing/limits first. To explicitly authorize a new
bounded attempt window after the fix, use:

```sh
python3 -m spotify_pipeline pilot --input cost_100.csv --execute-paid --budget-usd 2 --retry-after-fix
```

Each window permits at most three attempts per task; invalid-output retries remain
limited to one. Prior failed calls, unresolved reservations, completed records and
successful task caches are retained. This flag is never applied automatically.
Recognized quota/billing errors stop immediately without useless transient retries.

`pilot_calls.jsonl` logs every attempted real pilot call, including failed calls.
Raw usage is retained. The calculator's subtotal includes known usage on failed
attempts, never assumes unknown usage is free, and does not add reasoning twice.
`usage.csv` maps mutually exclusive billing items to local call IDs. The rate
card records currency, units, check date and an official source URL.

`pilot_summary.json` records cold/warm wall time, input checksum and IDs, exact
text reuse, model/settings, throughput, counts and zero-new-call warm evidence.
Cold elapsed time includes the interruption and restart. If a user manually
resumes much later, cold wall time includes that gap; active time is separate.

`diagnostics_calls.jsonl` and `diagnostics.json` are separate paid synthetic-input
tests, excluded from business aggregates and pilot projections. They share the
same US$2 global ledger. Synthetic-provider unit tests live only in `evals/`.
`budget_ledger.json` reports actual known charges plus retained reservations.

To watch the actual subprocess output recording, install an asciicast viewer
and play `artifacts/runs/pilot-100-v2/recovery.cast`; the text is also readable
line by line as JSON. No model execution is needed to view it.

Projections use 660,622 input rows, 660,609 nonempty classifications and 13 empty
quarantines. The exact-reuse scenario models 484,189 unique nonempty texts;
the no-reuse scenario models 660,609. Verification is 20% of distinct language
tasks. Group naming and memo generation are fixed overhead once each. The
conservative case assumes at least 10% retries and 50% slower request durations.
No stronger-model fallbacks or Batch discounts are assumed. Refresh measurements
at 500 and 10,000 before considering a full run; these are estimates only.
