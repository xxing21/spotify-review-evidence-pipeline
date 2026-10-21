# 16-worker, 20-review feasibility pilot

This is a separate paid experiment, `scaling-500-16w-v1`, on 500 fresh unique
nonempty source texts excluding all golden texts and previously cached texts.
Original supplied inputs and earlier measurement files are preserved.

The first request checks twenty-review compatibility on one worker. The remaining
480 reviews run through a persistent queue with a sixteen-worker limit. One hundred
seeded original source IDs are independently checked through GPT Decisions using
the unchanged rubric, with two reviews per request and up to eight verifier workers.
Grouping, ranking and memo stages use the same bounded evidence rules.

Actual source preparation plus active processing: 61.44 seconds. Main enrichment:
480 reviews in 22.88 seconds, with sixteen overlapping requests observed. Known
API cost: US$0.038659410, all usage available. One invalid memo response was retried
once. There were no failed enrichment or verification attempts. The US$0.25 pilot
cap and US$10 shared cap include all attempts; historical unknown charges remain
reserved in the shared ledger. Costs are usage-based estimates, not invoices.

```sh
# Offline; no API key or model calls
python3 -m spotify_pipeline scaling-replay --directory cost/scaling_500_16w
python3 scripts/audit_scaling.py --variant sixteen
```

Use `--rates /path/to/rates.csv` for editable-rate replay, or `--volume 200000`
to change only the projected volume. Saved summaries and per-attempt calls are
measurements; calculator.json, usage.csv and report.md are derived artifacts.

The primary two-review verifier baseline now forecasts **111.9 minutes / US$6.47**
with estimated exact-text reuse, or **184.5 minutes / US$7.12** conservatively.
The original 80.2 / 132.1-minute burst-based estimate is superseded and archived
in `initial_short_pilot_projection.json`. Current forecasts impose the local
sustained limits of 600 requests/minute and 600,000 tokens/minute.

A bounded additional trial, `scaling-500-16w-verify10-v1`, independently rechecked
the SAME 100 source IDs using ten reviews per request. It completed 10 calls in
3.33 seconds for US$0.01209220. Parent labels, predictions, calls and timings are
unchanged; no additional enrichment reviews were processed. Both experiments
together cost **US$0.050751610**, within the combined US$0.25 pilot allowance.
All trial usage is available. The global shared ledger is US$0.717121940,
including historical unresolved reservations.

The candidate forecast combines parent enrichment/grouping/memo measurements
with this trial's verifier measurements. It is NOT a measured composite cold run.
With estimated reuse: **102.9 minutes / US$5.93** base, **169.5 minutes / US$6.52**
conservative. Without reuse: **120.1 / 198.0 minutes**, **US$6.90 / US$7.59**.
Verification remains 20% of original IDs. The conservative case includes at
least 10% retries and 50% slower throughput. **Under two hours is feasible, not
guaranteed.** Larger-run queue, ingestion, export and database overhead has not
been measured. The offline proposed 100k sample has 78,288 distinct texts
and 21,712 aliases; the current projections use these measured counts. No target
classification was performed. Reproduce using `python3 scripts/profile_100k.py`.
The superseded corpus-ratio forecasts remain in `corpus_ratio_projection.json`. No fallback or provider Batch discount is assumed.

The trial's topic/intent/severity consistency is 78% / 92% / 78%; this compares
models within the same family, not independent human truth. Grounded entities
and quotes use the same deterministic extraction and do not prove semantic
accuracy. Raw responses and independently reproducible predictions are saved in
`artifacts/runs/scaling-500-16w-verify10-v1/`. Run the offline acceptance with
`python3 scripts/audit_verification_trial.py`.

Workers and batch size changed together on different fresh texts. This measures
the combined configuration, not the isolated causal speedup from more workers.
The new batch-aware label configuration preserves the old caches and human
evaluation; no new human accuracy result is claimed. All source IDs, record
hashes, fixed topic issues, scores and claim references pass the supplied checker
for this 500-ID scope. This does not establish 100k/full-corpus completion.

Actual stdout was recorded during execution under
`artifacts/runs/scaling-500-16w-v1/terminal/` in asciinema v2 format. Its checkpoint
is a stage boundary, not an additional claimed interruption demonstration. The
original 100-review real interruption/resume evidence remains preserved.
