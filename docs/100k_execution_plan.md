# 100,000-review execution constraints

Recorded October 20, 2026 from the user's additional requirement. This is a
plan for the 100k milestone, not evidence of a launched 100k run. The separate
[500-review scaling pilot](../cost/scaling_500/report.md) has now completed.
Its measured eight-worker forecast is **US$6.61–6.98 and 3.39–5.53 hours with reuse**;
the earlier existing-pipeline forecasts below are preserved as historical planning.

## Approved verification update

The user approved **5%**, replacing the previous 20% target for future 100k
execution. Classify 100,000 nonempty original IDs; independently re-label a seeded
random sample of 5,000 without showing enrichment predictions. The assignment
requires a declared independent sample but gives no minimum percentage. Keep all
50 human labels/evaluation, disagreement inspection, planted-error and injection
tests. All completed pilots keep their recorded settings and results.

The machine-readable [run plan](../cost/planning_100k/run_plan.json) declares
16 enrichment workers, 20-review enrichment batches, 10-review verification
batches, 5% verification, zero fallback and the US$10 shared API ceiling.
[Updated estimates](../cost/planning_100k/approved_report.md): **72.6 minutes /
US$4.12** base; **119.6 minutes / US$4.53** conservative with measured input reuse.
Including existing work/reservations gives US$4.83 / US$5.25. Local overhead at
100k is not measured, so the two-hour target is not guaranteed. Refresh offline:
`python3 scripts/refresh_100k_plan.py`. No paid 100k run is started by this change.

The 20% measurements and estimates below are historical baselines.

## Updated runtime preference

**Measured update:** the [16-worker/20-review pilot](../cost/scaling_500_16w/report.md)
completed 500 fresh reviews plus 100 independent checks. Its subsequent bounded
verification trial used ten-review batches on the same 100 IDs. The candidate
forecast combines these separately measured stages: **102.9 minutes / US$5.93**
base and **169.5 minutes / US$6.52** conservative with the proposed sample’s measured exact-text reuse.
The base case meets the target; the conservative case exceeds it. Current
forecasts impose sustained request/token limits instead of extrapolating burst
capacity. The primary two-review verifier baseline is **111.9 / 184.5 minutes**.
The superseded 80.2 / 132.1-minute estimate is archived with its original data.

The user requests **under two hours if possible for the 100k run**, retaining the
US$10 shared API ceiling. Treat two hours as a performance target, not a measured
promise or permission to exceed the budget. The user separately approved 5% verification above.

The following calculation predates the sixteen-worker benchmark. At the then-measured verifier rate and estimated reuse fraction, enrichment had to rise
from approximately 6.71 to 12.37 reviews/second, about 1.84 times the observed
eight-worker rate. A perfect doubling of enrichment throughput with sixteen
workers, retaining current verifier speed, models approximately 1.87 hours before
additional preparation overhead. This leaves little margin and is not evidence
that sixteen workers achieve that speed.

The tested optimization candidates were a bounded sixteen-worker pool and
twenty-review Responses batches, retaining the 4,096 output cap, exact ID/schema
validation, persistent queue, bounded retries and one shared spending ledger.
Both are implemented and tested in the separate fixed 500-review pilot. A ten-review Decisions verifier batch is also tested; its usage and timing replace the verifier basis only in the candidate projection.
Use the approved 5% independent verification for future execution. The proposed seeded 100k inputs are profiled offline: 78,288 distinct texts and
21,712 exact duplicates. Their original IDs are saved in
`cost/planning_100k/proposed_100k_ids.csv`. Adopt this selection or reprofile the
final inputs; a lower duplicate fraction changes both cost and time.
Do not use the other student's runtime as a prediction for this different setup.

The saved [runtime target calculation](../cost/planning_100k/runtime_target.json)
is offline and made no additional paid calls. The completed eight-worker pilot
and its 3.39–5.53-hour forecast remain unchanged.

## Scope and budget

- Target at least 100,000 successfully classified nonempty original review IDs;
  retain the full ingestion profile and explicit handling of all 13 empty texts.
- US$10 maximum across the 100k campaign, including decision calls, enrichment,
  independent verification, grouping, memo, failed calls, retries and any tests
  charged to that campaign. Restarts do not create a fresh allowance.
- Conservatively count the existing shared ledger, currently US$0.717121940 in
  known costs plus unresolved reservations, against that US$10 as well.
- Plan routine work to stay below US$8 total, leaving headroom for repairs and
  unknown charges. Do not interpret the headroom as permission for unlimited retries.
- Before every dispatch, atomically reserve a conservative maximum charge in the
  shared ledger. Admit no call if spent plus all reservations plus the next
  reservation would exceed US$10. Unknown timeout charges retain reservations.
- If the ceiling prevents completion, preserve pending work and report actual
  coverage. Do not exceed the cap to reach the target.
- API processing is the budget scope. Report hosting/local compute separately;
  do not start paid hosting purchases under this API authorization.

## Proposed model combination

The completed pilot uses Luna Responses for structured enrichment, grouping and
the grounded memo, combined with independently prompted GPT Decisions verification
on 20% of source rows. Decisions verifies topic/intent/severity and the remaining
required fields; it receives original text and rubric without enrichment answers.
The endpoint combination has been measured; it is not proven to improve accuracy.
Jev and Haiku are alternatives,
not additional mandatory providers; no second credential is needed for the chosen
OpenAI path.

Decisions returns choices/probabilities; it does not replace the complete required
record schema, exact evidence validation or integer severity contract. If used for
severity, select among explicit values 1–5 and validate the integer. Do not round
its probability-weighted `score` into a severity label. Treat confidence as a
signal requiring calibration, not proven correctness. Never supply enrichment
predictions to the independent verifier.

This changes the label-affecting configuration. Version the decision prompt,
endpoint, routing rules, model/settings and extraction policy in cache keys.
Reuse older results only where label-affecting settings match, with provenance;
do not claim unchanged-settings reuse across a changed classification method.
Keep the original human evaluation. If this design is tuned using reviewed
golden examples, disclose that use and obtain fresh human examples before
claiming independent final accuracy.

## Cost and throughput techniques

1. **Cache first:** exact original text plus all label-affecting settings identifies
   reusable predictions. Preserve every original ID. Reuse completed same-ID work
   and downstream artifacts when their inputs and settings match.
2. **Batch reviews:** begin with the validated ten-review request size. Measure
   larger batches before adopting them; never exceed 50 reviews or the output cap.
   Larger batches must still validate the exact ID set and complete response.
3. **Persistent queue:** one active task per exact-text/configuration key; workers
   claim tasks transactionally. Persist attempts and reservations before sending.
   Do not silently redispatch a task with an uncertain provider outcome after a crash.
4. **Bounded parallel workers:** implement a configurable worker pool with eight
   as the initial scaling target and sixteen as a conditional upper test point.
   Ramp through two, four and eight workers; try sixteen only if measured throughput
   continues improving within actual account limits. Reduce concurrency on
   throttling or overload. Share request/token rate limiting,
   spending reservations and retry policy. Parallelism speeds work; it does not
   itself reduce token prices or guarantee a proportional speedup.
5. **Separate task batching from provider Batch API:** grouped synchronous requests
   can work toward tonight's deadline. OpenAI's asynchronous Batch API offers a
   50% price discount but has a 24-hour completion window; do not promise tonight's
   completion or apply its discount to Standard requests. Do not assume Decisions
   can be sent through Batch: the current Batch guide does not list that endpoint.
6. **Bound paid work:** maintain the 4,096 output-token limit and bounded retries.
   Use the approved 5% verification, stronger-model fallback at 0%, and grouping/memo
   bounded. Reserve any new decision benchmark before running it under the same cap.

## Offline estimate

The separate [projection](../cost/planning_100k/projection.json) uses saved 10,000
checkpoint usage and the unchanged dated Standard rate card:

| Scenario | Estimated API cost | Estimated single-worker time |
|---|---:|---:|
| Exact-text reuse, base | US$4.47 | 17.57 hours |
| Exact-text reuse, conservative | US$4.75 | 27.98 hours |
| No exact-text reuse, base | US$5.74 | 22.75 hours |
| No exact-text reuse, conservative | US$6.09 | 36.17 hours |

These are estimates for 100,000 source rows, with duplicate/empty fractions scaled
from the corpus. The actual run must select at least 100,000 nonempty IDs and
recalculate using its exact distinct-text profile. They describe the existing
four-role Standard pipeline, not measured performance of the proposed Decisions
combination or parallel implementation. They exclude unknown charges, new decision
calls and unmeasured hosting/local costs. The conservative scenario includes at
least 10% retries and 50% slower throughput. Verification remains 20% of source
rows. Original pilot measurements and projections were not overwritten.

## Implementation status after the scaling pilot

Exact-text caching, ten-review Responses requests, SQLite state, original-ID
provenance, bounded retries and single-worker reservations already existed. The
new scaling pilot now implements the shared queue, up to eight workers, Decisions
verification and transactional US$0.25/run plus US$10/global reservations. Its
eight-worker peak, zero-call warm replay and offline calculator checks passed.
Eight initial Decisions requests were rejected; smaller requests fixed the
verification contract without relabeling completed enrichment. Their unknown
charges remain reserved and the checker flags them for review.

The sixteen-worker pool and twenty-review batching are also now tested under the
same spending controls. The 100k entry point and final input selection remain
unimplemented. The legacy
paid commands retain their US$2 pilot limits. No 100k paid work has started.

## Official sources checked October 20, 2026

- [GPT Decisions](https://developers.openai.com/api/docs/guides/decisions): fixed
  choices and rubric scores; Luna input-only pricing of US$0.10 per million tokens.
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna): Standard
  input US$0.10 and output US$0.50 per million tokens, plus cache pricing.
- [Batch API](https://developers.openai.com/api/docs/guides/batch): discounted
  asynchronous processing with a 24-hour completion window and supported endpoints.
- [Rate limits](https://developers.openai.com/api/docs/guides/rate-limits): shared
  organization/project request and token limits, response headers and gradual ramping.
