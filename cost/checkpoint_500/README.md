# 500-review checkpoint

This is an incremental extension of the measured 100-review pilot, not a new
fresh-cache 500-review cold experiment. The original `cost/` measurements remain
separate and unchanged.

```sh
# Explicit paid execution, same shared US$2 ledger
python3 -m spotify_pipeline checkpoint --input checkpoint_500.csv --execute-paid --budget-usd 2

# Offline cost and projection replay
python3 -m spotify_pipeline cost replay --directory cost/checkpoint_500

# Deterministic ranking and the zero-API instructor check
python3 -m spotify_pipeline rank --run-id pilot-500-v2
python3 -m spotify_pipeline check --run-id pilot-500-v2
```

The supplied file has 500 nonempty reviews and 479 distinct exact texts. Its first
100 rows are the original measured pilot. Those original IDs and classifications
are imported without new enrichment calls, under identical classification
settings. New exact duplicates reuse a direct original result while retaining
separate review IDs and business counts. There are 379 new distinct texts to
classify, producing 400 additional completed review IDs when successful.

Independent verification selects 100 original review IDs (20% of the 500 source
rows), without seeing enrichment predictions. Group names and the recommendation
are regenerated from the expanded aggregates. Classification instructions remain
unchanged to keep the 100- and 500-review checkpoints comparable; known topic
boundary errors are not assumed to disappear because the sample grew.

`pilot_calls.jsonl` contains only this checkpoint's new attempted calls. Its
usage and incremental API cost exclude inherited calls. `inherited_calls.jsonl`
preserves the original 100-review enrichment call evidence without changing
request IDs, phases, timestamps or usage. Those calls are not inserted into the
spending ledger a second time. The grading export combines historical and new
evidence so every completed original ID has provenance.

`pilot_summary.json` distinguishes inherited original IDs, new completed IDs,
new distinct language tasks, exact-text aliases, incremental elapsed time, and
warm replay. No fresh-cache cold time is claimed. Full-run projections divide
enrichment usage/time by the 379 newly classified texts, rather than all saved
outputs, and verification by its declared source-row sample. Fixed group/memo
overhead is added once. Projections are estimates, not permission for a full run.

The original 20-ID interruption snapshot and recording remain in the inherited
lineage. A new interruption is also performed after saved extension progress
(at least 120 completed IDs, including the imported 100), then resumes to 500.
See `checkpoint_extension_before.json`, `checkpoint_extension_after.json`, and
`recovery.cast` in `artifacts/runs/pilot-500-v2/`. The original recording is
retained as `recovery_inherited.cast`.

Human golden labels and the final human inspection remain pending. No 10,000
checkpoint, full-corpus classification or dashboard deployment starts here.
