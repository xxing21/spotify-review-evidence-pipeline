# Spotify Insight Pipeline — pilot first

This repository implements an auditable Python + SQLite review pipeline with four
separate model roles. It has completed the 10,000-review development checkpoint;
earlier 100/500 evidence is preserved.
**It is not a completed final-assignment submission.** No full classification or
web deployment has been performed.

## Current 100k plan: 5% independent verification

The user approved **5% independent verification** for the future 100k run:
classify all 100,000 nonempty original IDs and independently check a seeded random
sample of **5,000**. The assignment specifies a declared random sample without a
minimum percentage. Keep the 50 human labels, planted-error/injection tests and
disagreement analysis. Completed pilots retain their actual 20% checks unchanged.

With the proposed input sample and tested batching, the new estimates are
**72.6 minutes / US$4.12** base and **119.6 minutes / US$4.53** conservative.
Including all currently recorded work and unresolved reservations gives
**US$4.83 / US$5.25**, below the unchanged US$10 ceiling. Larger-run local overhead
is unmeasured; the conservative estimate leaves little time margin under two hours.
These are offline projections; no 100k paid run has started.

- [Approved plan](cost/planning_100k/run_plan.json)
- [Updated report](cost/planning_100k/approved_report.md)
- [Offline calculation](cost/planning_100k/approved_projection.json)

```sh
python3 scripts/refresh_100k_plan.py
```

The 20% figures below document the completed pilot configuration and are retained
as historical comparisons, rather than the current 100k plan.

## Latest feasibility pilot: 16 workers and 20-review requests

The separate `scaling-500-16w-v1` experiment completed **500 fresh unique source
reviews** and **100 independent Decisions checks**. Sixteen overlapping enrichment
requests were observed. The original eight-worker experiment and earlier
100/500/10,000 evidence remain unchanged.

| Measurement | Actual result |
|---|---|
| Source preparation plus active processing | **61.44 seconds**; process startup excluded |
| Active pipeline processing | 57.09 seconds |
| Main enrichment stage | **480 reviews in 22.88 seconds**, 20.98 reviews/second, 16 concurrent calls |
| Request size and response bound | 20 reviews; strict schema/ID validation; 4,096 output tokens |
| Primary pilot usage-based API cost | US$0.038659410; all usage available |
| Primary calls | 78 attempts; one memo invalid-output retry; no failed enrichment or verification attempts |
| Additional verifier batching trial | Same 100 source IDs, 10 reviews/request, 10 calls, 3.33 seconds, US$0.01209220 |
| Combined actual API cost | **US$0.050751610**; no unresolved charges for these two experiments |
| Warm replay | 0.104 seconds; **zero new model calls** |
| Validation | Supplied checker passes for 500-ID scope; 37 offline tests pass; portable calculator and ranking agree |
| Shared budget | **US$0.717121940** known costs plus historical unresolved reservations across all work, below US$10 |

The tested candidate combines Luna Responses enrichment with ten-review GPT
Decisions verification batches, retaining independent checks on 20% of source IDs.
Its **100k estimates with exact-text reuse** are **102.9 minutes / US$5.93** base
and **169.5 minutes / US$6.52** conservative. These are derived from separately
measured stages, not a combined cold execution. Including existing work and
reservations without subtracting possible reuse gives **US$6.65–7.24**. Without
reuse the estimates are **120.1 minutes / US$6.90** and **198.0 minutes / US$7.59**.

The primary two-review verifier baseline is **111.9 / 184.5 minutes**, with
US$6.47 / US$7.12 estimated API spend and reuse. The initial 80.2 / 132.1-minute
projection extrapolated short burst capacity and is superseded; its original
artifact is retained as `cost/scaling_500_16w/initial_short_pilot_projection.json`.
Both current estimates respect the local sustained 600 requests/minute and
600,000 tokens/minute ceilings; burst speed is not extrapolated indefinitely.

**Under two hours is feasible in the base forecast, not guaranteed.** An offline
proposed 100k sample contains 78,288 distinct texts and 21,712 exact duplicates;
these counts now drive the reuse estimates. Sustained throughput and larger-run
local overhead still need checking. Adopting a different selection requires a new profile. The twenty-review configuration has its own batch-aware cache
identity; earlier ten-review human agreement does not certify its accuracy.
Primary independent agreement is topic 80%, intent 89%, severity 74%, with 44
core disagreements retained. The ten-review verifier trial gives 78%, 92%, 78%
respectively. Both measure consistency within the same model family, not human
accuracy. No business labels were silently replaced.

- [Measured report and offline calculator](cost/scaling_500_16w/report.md)
- [Feasibility assessment](evals/scaling_500_16w/feasibility.json),
  [processing acceptance](evals/scaling_500_16w/acceptance.json),
  [verifier trial acceptance](evals/scaling_500_16w/verification_batch_trial_acceptance.json),
  [supplied checker](artifacts/runs/scaling-500-16w-v1/self-check.json)
- [Concurrency evidence](evals/scaling_500_16w/concurrency.json),
  [actual terminal recordings](artifacts/runs/scaling-500-16w-v1/terminal/)
- [Independent comparisons](evals/scaling_500_16w/verification_review.json),
  [offline tests](evals/scaling_500_16w/offline_tests.json),
  [clean keyless replay](evals/scaling_500_16w/clean_replay.json)

```sh
# Completed fixed experiments are reused; no new cold pilot is launched.
python3 -m spotify_pipeline scaling-pilot --variant sixteen --execute-paid
python3 -m spotify_pipeline scaling-pilot --variant sixteen --verify-batch-trial --execute-paid

# Offline only
python3 -m spotify_pipeline scaling-replay --directory cost/scaling_500_16w
python3 scripts/audit_scaling.py --variant sixteen
python3 scripts/audit_verification_trial.py
# Rebuild the proposed input profile locally; no classification/model calls:
python3 scripts/profile_100k.py
```

The paid 100k run has not started. Its larger-run entry point and final input selection,
plus the deployed application and public submission, remain later work.

## Latest scaling experiment: 500 fresh reviews, up to eight workers

The separate `scaling-500-v1` experiment completed **500 fresh, unique source
texts** plus **100 independent checks**. Luna Responses performs enrichment,
grouping and memo writing; GPT Decisions performs independently prompted
verification using original text and the shared rubric. It does not see enrichment
predictions or human answers. Existing 100/500/10,000 measurement files and the
original human labels/predictions are unchanged.

| Measurement | Result |
|---|---|
| Active processing across both attempts | 122.15 seconds, including failed calls and repaired verification; preparation, process startup, development and approval waiting excluded |
| Eight-worker enrichment stage | 320 reviews in 47.66 seconds; eight overlapping requests confirmed |
| Known recorded API usage | US$0.041287690 |
| Unknown charges | Eight rejected Decisions requests; US$0.04533560 remains reserved |
| Shared ledger across all experiments | US$0.666370330 including unresolved reservations, under the US$10 ceiling |
| Pilot limit | US$0.25 including its retries and unknown reservations |
| Warm replay | 0.096 seconds, zero new calls |
| Independent agreement | Topic 80%, intent 94%, severity 71%; same-model consistency, not human accuracy |
| Checker | Record/hash/ranking checks pass; `review_required` for 16 missing usage fields across eight requests |

The initial Decisions request arrays were rejected. Verification was repaired
with smaller requests and five sentiment levels, preserving all 500 enrichment
records, failed calls and reservations. The original verifier configuration and
the versioned runtime override are saved separately. One memo response also needed
its permitted invalid-output retry. The original 100-review interruption recording
remains the recovery deliverable; this experiment's 40-record checkpoint is a ramp
stage boundary, not a newly claimed interruption demonstration.

The revised **100,000-review estimate** with exact-text reuse is **US$6.61 / 3.39
hours** in the base case and **US$6.98 / 5.53 hours** conservatively. Without reuse
it is US$7.95 / 4.49 hours and US$8.45 / 7.36 hours. These are forecasts from the
measured eight-worker phases and assume 20% source-row verification. The reuse
fraction is estimated from the full corpus, not an already selected 100k subset.
Unknown charges, hosting/local compute and prior experiments are outside those
forecast subtotals; the shared US$10 execution ceiling still counts prior recorded
costs and reservations. The decision-based verifier costs more per checked review
than the earlier ten-review Responses verifier in this experiment; the combination
remains within the budget forecast and does not establish better label accuracy.

- [Measured scaling report and calculator](cost/scaling_500/report.md)
- [Processing/control acceptance](evals/scaling_500/acceptance.json),
  [concurrency evidence](evals/scaling_500/concurrency.json)
- [Independent comparisons](evals/scaling_500/verification_review.json),
  [inspected differences and actual failures](evals/scaling_500/error_analysis.md),
  [checker](artifacts/runs/scaling-500-v1/self-check.json)
- [Saved ranking](artifacts/runs/scaling-500-v1/ranking.csv),
  [pilot memo](artifacts/runs/scaling-500-v1/memo.md),
  [versioned verification repair](artifacts/runs/scaling-500-v1/verification_contract_repair.json)

```sh
# Existing completed experiment is reused; no new 500-review run is opened.
python3 -m spotify_pipeline scaling-pilot --execute-paid

# Offline, portable calculator; no API key/model calls.
python3 -m spotify_pipeline scaling-replay
python3 scripts/audit_scaling.py
```

**The 100k paid run has not started.** Its input selection and larger-run entry
point still need implementation; the dashboard/backend/database deployment and
public submission remain incomplete.

## Latest checkpoint: 10,000 reviews

**All 10,000 supplied development reviews are classified; zero remain pending or
quarantined.** Full-file ingestion still covers 660,622 original rows, while
classification stops at the 10,000-review sample. This is not a completed final
submission or a full-corpus recommendation.

| Result | Measured outcome |
|---|---|
| Final run | `pilot-10000-v3`; original `analysis_10000.csv` unchanged |
| Coverage | 10,000 validated original IDs; all source hashes match |
| Earlier work | The original 500 results are retained; all 9,620 valid results from the interrupted extension were preserved |
| New enrichment | 7,970 text/configuration work units; the file contains 8,448 distinct texts |
| Exact-text reuse | 1,551 direct cache aliases with original IDs preserved |
| Incremental execution | 6,949.37 seconds / **115.82 minutes**, including both attempts and restart |
| Recorded usage-based API estimate | **US$0.478451525** across 1,034 actual new attempts, including 35 failed attempts |
| Unresolved request charges | 15 failed requests; **US$0.049552125** conservatively reserved, separate from known usage |
| Shared budget ledger at the 10,000 checkpoint | **US$0.577325415** known costs plus unresolved reservations across all experiments, under US$2 |
| Warm replay | **0.715 seconds**, 10,000 saved records, 202 saved downstream tasks, **zero new API calls** |
| Independent verification | 2,000 source reviews; 397 topic/intent/severity disagreements; 1,280 any-field differences |
| Human inspection flags | 2,362 retained reviews; no selective removal from business counts |
| Offline validation | 28 tests pass; portable ranking identical; doubled rates double known API subtotal; volume edits preserve measurements |
| Instructor checker | `review_required` only for 30 missing token fields across 15 requests; all record/cache/hash/ranking checks pass |
| Human golden evaluation | Complete: 50 human labels and 50 predictions; topic 82%, intent 88%, severity 66% agreement |

The sample contains 3,855 complaints, 400 cancellation/departure statements,
4,255 praise reviews, 345 requests and 1,145 unclear reviews. Intent labels are
mutually exclusive; cancellation statements do not establish observed churn.
The weighted ranking puts usability first (**1,358 reviews; score 3,504**),
playback second (**661; 2,149**), broad other complaints third (**1,010; 1,991**),
and billing fourth (**647; 1,833**). Each issue number resolves to its
`ISSUE-<TOPIC>-complaint_count` or `ISSUE-<TOPIC>-priority_score` claim in the
saved claims table.

The preliminary recommendation is to investigate unwanted playback and difficult
controls, with playback reliability as the strongest alternative. The usability
count covers controls, layout, ads and other behavior; the examples do not
measure the prevalence of autoplay problems. Premium-control topic errors and
privacy allegations require inspection before a product investment.

### Recovery and configuration provenance

The first extension (`pilot-10000-v2`) stopped on HTTP 400 with 9,620 completed,
80 quarantined and 300 pending. UUID copying errors exhausted the original
invalid-output retry policy on eight batches. A tested request-specific ID enum
fixed the transport contract. The human user explicitly approved a third and
final attempt for those 80 reviews. Each used exactly three total attempts and
succeeded; completed IDs were never reclassified.

New responses use schema version `spotify-label-v3-id-enum` and a distinct cache
key. Inherited v2 outputs retain their original `label_config` and call evidence.
The label prompts, model, Standard tier, effort and label definitions are
unchanged. One repeated text required a new classification under the different
schema: 7,970 new work units cover 7,969 distinct new texts. These are nested,
mixed-transport development results, not independent experiments or evidence of
improved accuracy. Prompt/extraction agreement is not human label accuracy.

Both attempts' actual costs and execution times are included in the checkpoint
measurement. Earlier 100/500 execution, development work and approval waiting
between invocations are excluded; subprocess restart overhead is included.
Original failed attempts and unknown usage remain visible. The instructor
checker correctly requests review of unavailable usage; no missing token count
was invented or replaced with zero. Raw usage times dated rates is an estimate,
not a reconciled invoice. Local computing costs remain unmeasured.

- [Plain-English results](artifacts/runs/pilot-10000-v3/results.md),
  [recommendation](artifacts/runs/pilot-10000-v3/memo.md),
  [assistant review](artifacts/runs/pilot-10000-v3/memo_review.md)
- [Ranking](artifacts/runs/pilot-10000-v3/ranking.csv),
  [claims](artifacts/runs/pilot-10000-v3/claims.csv),
  [source-to-claim trace](artifacts/runs/pilot-10000-v3/trace.md)
- [Measured cost/time and projections](cost/checkpoint_10000/report.md),
  [offline replay guide](cost/checkpoint_10000/README.md),
  [earlier attempt snapshot](cost/experiments/pilot-10000-v2/)
- [Instructor checker](artifacts/runs/pilot-10000-v3/self-check.json),
  [grading export](artifacts/runs/pilot-10000-v3/grading/),
  [acceptance status](evals/checkpoint_10000/acceptance.json)
- [Independent comparisons](evals/checkpoint_10000/verification_review.json),
  [inspected limitations](evals/checkpoint_10000/error_analysis.md),
  [clean offline replay](evals/checkpoint_10000/clean_replay.json)
- [Real recovery recording](artifacts/runs/pilot-10000-v3/recovery.cast),
  [repair authorization](evals/checkpoint_10000/recovery_authorization.json)

```sh
# Resume/reuse the completed recovery; the explicit final-attempt flag records
# the authorization already given. No completed ID is sent again.
python3 -m spotify_pipeline recover-checkpoint --execute-paid --budget-usd 2 --allow-final-invalid-attempt

# These commands are entirely offline, with no API key required
python3 -m spotify_pipeline cost replay --directory cost/checkpoint_10000
python3 -m spotify_pipeline rank --run-id pilot-10000-v3
python3 -m spotify_pipeline check --run-id pilot-10000-v3
python3 scripts/inspect_run.py pilot-10000-v3
python3 scripts/audit_checkpoint.py
```

`check` and `audit_checkpoint.py` intentionally exit nonzero while billing usage
is unresolved; inspect their saved JSON rather than interpreting this as missing
classifications. The legacy v2 paid checkpoint entry refuses to restart once the
ID-constrained recovery exists, preventing accidental duplicate work.

Updated full-run estimates are **US$29.52 / 115.79 hours** with exact reuse in
the base case and **US$31.40 / 184.51 hours** conservatively. Without reuse they
are **US$37.92 / 150.01 hours** and **US$40.26 / 238.65 hours**. These extrapolate
known reported usage; unknown charges are excluded and separately reserved.
They are estimates, not all-inclusive quotes or authorization for a larger run.
Verification remains 20% of original source rows; fallback remains zero.

All 50 human labels and all 21 topic/intent/severity disagreement decisions are
saved. See the [review summary](evals/golden_adjudication_results.md) and
[submission readiness checklist](docs/submission_readiness.md). Two previously
flagged rubric questions remain visible. Full classification, public publication
and deployment remain later work.

### Completed human reference review

All 50 human labels are saved separately in `evals/golden_labels.json`. Only
after the last human answer was saved did the model classify the 49 distinct
reference texts, with one exact-text alias preserving 50 original IDs. Its
requests contained original review ID/text only; human answers and notes never
entered model prompts or result caches. The saved run uses the 10,000 checkpoint's
v3 model/prompt/schema settings.

| Comparison with human choices | Agreement |
|---|---|
| Topic | 41/50 — 82% |
| Intent | 44/50 — 88% |
| Severity | 33/50 — 66%; mean absolute difference 0.40 on the 1–5 scale |
| Sentiment | Mean absolute difference 0.238 on the -1 to +1 scale |

The original comparison contains seventeen severity differences: AI higher on
15, lower on 2. All 21 topic/intent/severity disagreement choices have since been
reviewed by the user: 12 retained human labels and 9 selected AI labels. Original
human answers and predictions remain unchanged. The table above reports agreement
before adjudication, not population accuracy; the reviewed choices are not new
independent accuracy evidence. The original human sample has no cases assigned
to access, billing or downloads.

Five calls cost **US$0.002421625**, with complete usage and no retries. Current
shared costs plus unresolved reservations across every experiment total
**US$0.579747040**, below US$2. Earlier checkpoint measurements stay unchanged.
Offline replay finds the matching saved golden predictions and makes no calls.

- [Readable human comparison and disagreements](evals/golden_results.md)
- [Full comparison](evals/golden_report.json), [separation/replay evidence](evals/golden_validation.json)
- [Evaluation cost and calls](cost/golden_evaluation/report.md)

```sh
# Offline: no API key or model calls
python3 -m spotify_pipeline evaluate --run-id pilot-10000-v3
```

No prompts have been tuned to these answers. If findings inform prompt changes,
disclose that use and collect fresh held-out human cases for final evaluation.

## Earlier checkpoint: 500 reviews

The 500-review checkpoint is complete and passes the instructor checker for its
500-ID scope. The original 100-review measurements below remain preserved.

| Result | Actual outcome |
|---|---|
| Coverage | **500 completed; zero quarantined or pending** |
| Saved work reused | 100 original classifications, without paying to enrich them again |
| New work | 379 distinct texts, plus 21 exact-text aliases, complete 400 additional original IDs |
| Incremental elapsed time | **389.78 seconds (about 6.5 minutes)**, including verification, analysis and restart |
| Incremental usage-based API estimate | **US$0.023235875**, across 50 new attempts; no new failed attempts |
| Warm replay | **0.050 seconds**, zero new model calls and zero incremental API cost |
| Independent verification | 100 source reviews; 18 topic/intent/severity disagreements; 53 with any-field differences |
| Human review flags | 105 retained records flagged; none silently excluded |
| Checks | Instructor checker passes; 25 offline tests pass |

This extends the earlier results; it is **not** a fresh-cache 500-review cold run.
Historical calls are retained as evidence, without being charged twice. The 500
source rows contain 479 distinct exact texts. Classification settings are
unchanged, and the 100-review sample is nested inside the 500; these are not
independent experiments or evidence that accuracy improved.

The expanded results contain 207 complaints, 25 expressions of leaving/cancelling,
216 praise reviews, 10 requests and 42 unclear reviews. The required weighted
ranking places **usability first (76 reviews, score 201), playback second
(43 reviews, score 142), and billing third (32 reviews, score 95)**. Counts and
scores are saved as `ISSUE-<TOPIC>-complaint_count` and
`ISSUE-<TOPIC>-priority_score` in the linked claims table. The recommendation
remains provisional: Premium-only restrictions can be misclassified as usability,
and human golden labels are still pending.

- [500-review recommendation](artifacts/runs/pilot-500-v2/memo.md),
  [review note](artifacts/runs/pilot-500-v2/memo_review.md),
  [ranking](artifacts/runs/pilot-500-v2/ranking.csv),
  [claims](artifacts/runs/pilot-500-v2/claims.csv)
- [Measured checkpoint cost/time and refreshed projections](cost/checkpoint_500/report.md),
  [replay guide](cost/checkpoint_500/README.md)
- [Checker result](artifacts/runs/pilot-500-v2/self-check.json),
  [grading export](artifacts/runs/pilot-500-v2/grading/),
  [source-to-claim trace](artifacts/runs/pilot-500-v2/trace.md)
- [Independent comparisons](evals/checkpoint_500/verification_review.json),
  [inspected limitations](evals/checkpoint_500/error_analysis.md)

```sh
# Same shared US$2 cap; repeating this command resumes/reuses saved work
python3 -m spotify_pipeline checkpoint --input checkpoint_500.csv --execute-paid --budget-usd 2

# Offline replay of the 500-review measurements and saved membership
python3 -m spotify_pipeline cost replay --directory cost/checkpoint_500
python3 -m spotify_pipeline rank --run-id pilot-500-v2
python3 -m spotify_pipeline check --run-id pilot-500-v2
```

The refreshed full-run estimate with exact reuse is **US$28.67 and 136.74 hours**
with one worker; the conservative case is **US$31.53 and 225.62 hours**. The
100-review estimate assumed verification of distinct texts; this checkpoint
models verification of 20% of original nonempty source rows, matching its actual
sampling frame. These are estimates only. Improve and remeasure throughput before
considering a full run. This is the earlier 500-review projection; the completed 10,000-review run above supplies the latest estimates. No deployment has started.

## Original 100-review pilot evidence

Final pilot run: **`pilot-100-v2`** (100 reviews, not the full corpus).

| Item | Actual result |
|---|---|
| Full source ingested/profiled | 660,622 original IDs; source checksum matches |
| Source quality | 13 empty texts quarantined; 159,701 missing app versions; zero duplicate IDs |
| Exact nonempty texts | 484,189 distinct; 176,420 duplicate rows retain their IDs |
| Final pilot coverage | **100 completed, 0 quarantined, 0 pending** |
| Model/settings | OpenAI `gpt-6-luna`, Standard, effort `none`, batches of ten, one worker |
| Cold time | **92.521 seconds**, including checkpoint/interruption/restart |
| Warm time | **0.023 seconds; zero new calls; US$0 incremental API cost** |
| Calculated pilot API spend | **US$0.006916075** from recorded usage and dated rates; invoice not reconciled |
| Calls | 15 attempts across four roles, including one rejected memo output and successful retry |
| Independent verification | 20 reviews; 5 topic/intent/severity disagreements; 12 with any-field differences |
| Recovery evidence | 20 saved completed IDs before interruption, 100 after resume; completed IDs not relabeled |
| Zero-API instructor checker | **Pass for the 100-review scope**; not a full-corpus coverage claim |
| Real injection/planted-error model tests | Both passed on separate synthetic inputs excluded from business counts |
| Offline tests | 25 passing synthetic-provider tests |
| Golden evaluation | Pending all 50 human labels; no human answers fabricated |
| Live dashboard/backend | Deferred; no live URL yet |

The baseline ranks usability first (16 complaints/cancellations, severity sum 44),
but assistant inspection found likely Premium-only-control topic errors in its
examples. Read the [provisional memo](artifacts/runs/pilot-100-v2/memo.md) alongside
[its review note](artifacts/runs/pilot-100-v2/memo_review.md) and the
[inspected failures](evals/pilot_error_analysis.md). No validated full-corpus
product priority is established.

An earlier development experiment (`pilot-100`) encountered HTTP 429 errors and
model-extraction validation failures, completing 60 reviews and quarantining 40.
Its evidence is retained under `artifacts/runs/pilot-100/` and
`cost/experiments/pilot-100-v1/`. The corrected prompts and deterministic extraction
policy use a separate fresh cache for the final measured experiment. Across all
experiments and both checkpoints, the latest shared costs and reservations are
reported in [the spending ledger](cost/budget_ledger.json). This ledger includes
US$0.009600 of unresolved reservations from the original failed requests, without
assuming they were free. These are calculated charges/reservations, not a
reconciled invoice.
The first errors recorded only HTTP status; their exact quota/rate cause is
unknown. Updated error handling safely distinguishes provider codes. See the
[official error guide](https://developers.openai.com/api/docs/guides/error-codes).

The original 100-review projections remain in `cost/report.md`. The 500-review
checkpoint refreshes them using newly measured work and an explicit source-row
verification sample; see the latest report linked above.

## Setup

Python 3.11 or newer is required; verified locally with Python 3.14.7. The pipeline
has **no third-party runtime dependencies**. The build dependency is pinned in
`pyproject.toml`; API calls use the standard-library HTTPS client with no hidden
SDK retries.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m spotify_pipeline --help
```

Commands also work directly from this folder with `python3 -m spotify_pipeline`.
Place the supplied dataset files here, unchanged. Their identity is recorded in
`manifest.json`; raw full CSV data and local SQLite files are excluded from Git.
The original supplied README is preserved as [README.dataset.md](README.dataset.md).

Keep the API key in a local `.env` file with `OPENAI_API_KEY=...`. Never put a real
key in chat, source, browser code or saved artifacts. The blank `.env.example`
lists the course-recommended names; this implementation uses only OpenAI.
`.gitignore` excludes `.env` and `.env.*`, except the blank example. No key is
needed for offline replay, ranking, human labeling or the checker.

## Run safely

```sh
# Full ingestion/profile only — no model calls
python3 -m spotify_pipeline prepare --input spotify_reviews_18months.csv

# Explicit paid cold/warm experiment on the fixed 100 rows
python3 -m spotify_pipeline pilot --input cost_100.csv --execute-paid --budget-usd 2

# Offline measurement replay and editable-volume projection
python3 -m spotify_pipeline cost replay
python3 -m spotify_pipeline cost replay --volume 100000

# Guided blind human labeling, then offline evaluation status
python3 -m spotify_pipeline label-golden
python3 -m spotify_pipeline evaluate --run-id pilot-100-v2

# Deterministic ranking from accepted membership, when available
python3 -m spotify_pipeline rank --run-id pilot-100-v2

# Instructor checker against the pilot scope (passes for the final pilot)
python3 -m spotify_pipeline check --run-id pilot-100-v2

# Save real outcomes of the offline synthetic-provider tests
python3 scripts/run_checks.py
```

If a future task exhausts its attempts due to account access, fix OpenAI billing/limits first,
then explicitly open a new bounded recovery window without deleting evidence:

```sh
python3 -m spotify_pipeline pilot --input cost_100.csv --execute-paid --budget-usd 2 --retry-after-fix
```

The same run retains failed calls, unknown-cost reservations, records and caches.
Completed IDs are never relabeled under unchanged settings. Each recovery window
has a maximum of three attempts per task and one invalid-output retry. Account
errors stop immediately. A global command lock enforces one paid worker, and all
actual calls share the US$2 spending ledger.

The pilot driver records a real worker interruption after 20 saved classifications,
then resumes the remaining inputs and runs warm with zero additional model calls.
**The final pilot recorded 20 completed IDs before interruption and 100 after
resume, with no new enrichment calls for checkpoint IDs.** Cold wall time includes
recorded restart overhead; active time is reported separately. The first failed
experiment and its account-repair wait are separate from this final measurement.

`run --input path.csv --run-id example --execute-paid` accepts arbitrary source-format
CSVs of 1–100 rows. Larger files are refused, never silently truncated. Golden IDs
are blocked from development runs. The explicit `checkpoint` command accepts only the supplied checksum-bound 500-row and 10,000-row files. Its default time limit remains 20 minutes; 180 minutes requires an explicit flag for the 10,000 checkpoint.
Full-corpus dispatch remains blocked. The completed 10,000-review recovery is resumed/reused with `recover-checkpoint`; its legacy v2 entry is superseded.

## Evidence map for the rubric

| Rubric evidence | Location | Status |
|---|---|---|
| Full identity, profile, missingness and empty quarantine | [Ingestion report](artifacts/ingestion/report.json), [profile](artifacts/ingestion/ingestion.json), [quarantine](artifacts/ingestion/quarantine.jsonl) | Complete |
| Architecture, code/model boundaries and role handoffs | [Architecture](docs/architecture.md), [role prompts](spotify_pipeline/prompts/), [contract](GRADING_CONTRACT.md) | Implemented |
| Original IDs, row hashes and record statuses | [Pilot records](cost/pilot_records.jsonl), local `state/pipeline.sqlite3` | 100 completed IDs preserved |
| Calls, settings, failures, usage and spending | [Pilot attempts](cost/pilot_calls.jsonl), [run summary](artifacts/runs/pilot-100-v2/run_summary.json), [ledger](cost/budget_ledger.json) | Final run usage complete; earlier failures/reservations retained |
| Cost/runtime calculator and offline replay | [Calculator guide](cost/README.md), [report](cost/report.md), [rates](cost/rates.csv), [arithmetic](cost/calculator.json) | Real cold/warm measurement and editable full-run projections |
| Retry, budget, recovery and arithmetic tests | [Test results](evals/system_checks.json), [test transcript](evals/system_checks.txt) | 25 synthetic-provider tests pass |
| Clean environment and secret checks | [Offline replay](evals/clean_replay.json), [secret check](evals/secret_check.json) | Installed package, no credentials or original database; rate/volume invariants pass; local key absent from deliverables |
| Human golden labels and fair evaluation | [Labeling guide](docs/labeling.md), [evaluation status](evals/golden_report.json) | Human labels pending |
| Independent verifier and real planted-error/injection tests | [Diagnostic status](cost/diagnostics.json) | Real independent verification and synthetic-input model diagnostics saved |
| Interruption/resume recording and snapshots | [Recording](artifacts/runs/pilot-100-v2/recovery.cast), [before](artifacts/runs/pilot-100-v2/grading/checkpoint_before.json), [after](artifacts/runs/pilot-100-v2/grading/checkpoint_after.json) | Real process interruption and resume demonstrated |
| Membership, baseline ranking and numerical claims | [Pilot grading export](artifacts/runs/pilot-100-v2/grading/) | 50 complaint/cancellation memberships, reproducible ranking and claims |
| Mechanical audit | [Self-check](artifacts/runs/pilot-100-v2/self-check.json) | Pass for final pilot; old experiment remains incomplete |
| Traceable memo and one-review end-to-end trace | [Memo](artifacts/runs/pilot-100-v2/memo.md), [trace](artifacts/runs/pilot-100-v2/trace.md), [review note](artifacts/runs/pilot-100-v2/memo_review.md) | Saved; semantic limitations disclosed |
| Required deployed dashboard/backend/database | Later milestone | Pending |

## Reproducible analysis

Classification uses only original review text and its routing ID. Code supplies the
complete original text as the exact quote and extracts literal feature-term spans;
raw model placeholders remain saved in handoffs. These deterministic fields do not
prove that the model labels are semantically correct. All source
metadata and exact instructor-compatible row hashes are preserved. Shared topics,
intent precedence and severity examples live in the saved prompts. Exact-text
reuse requires the same model, effort, prompt, schema, output cap and processing
tier, and points directly to an original completed record; business counts keep
every source ID.

The independent verifier receives a seeded random 20% sample without the first
prediction. Code compares results; same-model agreement does not prove accuracy.
Code groups each complaint/cancellation into one stable topic-based issue.
The grouping model names issues from at most three examples per issue without
changing membership. The baseline is `priority_score = severity_sum`, exactly
count × mean severity, sorted by descending score then ascending issue ID.
Means use six decimals with half-up rounding. Praise, requests and unclear records
are excluded from ranking.

The memo model receives only saved aggregates and a bounded evidence pack. Code
validates issue/review/claim references and renders numbers from saved claims.
Humans still inspect whether quotes and the argument support the recommendation.
The ranking command uses saved membership and records without calling a model.
If the local SQLite database is absent, it reads the saved JSONL/CSV artifacts
instead. The clean replay check verified byte-identical ranking and unchanged raw
measurements; doubled rates doubled calculated API spend without changing time.

## Limitations and remaining assignment work

This historical, self-selected review dataset is not Spotify's complete customer
population. Cancellation language is expressed intent, not observed churn. There
is no account revenue, reliable plan tier or causal retention estimate. The first
and last calendar months are partial. Broad topic issues are a pilot baseline,
not a fine-grained discovery of individual defects.

Before submission: complete human golden labels and inspect the evaluation; review
the documented label failures and 500-review findings; then use the completed
10,000-review checkpoint to review quality and refresh projections before any final-scale run;
authorize the final classification scope and budget; deploy the database, backend
and dashboard; publish evidence and a public GitHub URL; verify access signed out.
The assignment brief mentions an at-least-100,000 option, while the supplied
machine contract targets all 660,622 IDs; no reduced final scope is assumed here.
No current evidence should be presented as a successful full-corpus run.

Dataset: [BwandoWando, version 2](https://www.kaggle.com/datasets/bwandowando/3-4-million-spotify-google-store-reviews),
publisher-listed CC0. Source extract SHA-256:
`1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.
Model/settings and current Standard prices were checked against the
[OpenAI model reference](https://developers.openai.com/api/docs/models/gpt-6-luna).
