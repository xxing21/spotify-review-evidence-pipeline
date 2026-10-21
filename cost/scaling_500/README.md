# Fresh 500-review scaling experiment

Run `scaling-500-v1` contains 500 previously unseen unique original texts and a
seeded independent verification sample of 100 source IDs. It is separate from
the original supplied 500-review checkpoint. Supplied inputs were preserved.

```sh
python3 -m spotify_pipeline scaling-replay
python3 -m spotify_pipeline scaling-replay --volume 200000
python3 scripts/audit_scaling.py
```

These commands make no model calls. Use `--rates /absolute/path/to/rates.csv`
for editable-price replay. `pilot_summary.json` and `pilot_calls.jsonl` are the
saved measurements; replay writes derived `calculator.json`, `usage.csv` and
`report.md`. Use the default volume to restore the standard 100k forecast.

`initial_attempt/` preserves the first incomplete attempt, including the failed
Decisions requests. The final logs retain all 111 attempts and their original
usage or unknown-usage status. Decisions is billed on input only; Responses uses
mutually exclusive input/cache/output categories. Unknown charges are never
replaced with zero. Local/hosting costs are unmeasured and separate.

The source selection initially used a slow SQLite sort and was interrupted
before any calls. Selection now streams the original checksum-validated CSV.
The reported 122.15 seconds is cumulative active pipeline processing across the
paid attempts, including failed requests and verification repair execution. It
excludes source preparation, process startup, implementation/debugging and
human/approval waiting. Phase measurements use disjoint inputs and differing
review lengths; speed ratios are diagnostics, not controlled identical-input
experiments. The larger 320-review eight-worker stage anchors the time forecast.

The verifier uses two reviews and ten questions per Decisions request. Sentiment
uses five ordered levels; the zero-based weighted index maps to -1..+1. Severity
is an explicit integer category 1..5, never a rounded weighted score. Request
arrays and mapping are versioned. The initial ten-review/21-level requests were
rejected; the exact rejected sub-array was not captured in those first errors.
No unsupported claim about the endpoint's precise maximum is inferred.

All stage outputs, raw handoffs, queue history, ranking, memo and grading export
are under `artifacts/runs/scaling-500-v1/`. Independent comparisons and budget,
concurrency, replay, privacy and record checks are under `evals/scaling_500/`.
The checker still requires review of missing token usage on eight rejected
requests. Data, source hashes, ranking and measured scaling checks pass.
