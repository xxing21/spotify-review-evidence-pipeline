# Scaling pilot inspection

All 500 original review IDs have schema-valid enrichment. The new independent
verifier checked 100 source IDs, with topic agreement 80%, intent 94% and severity
71%. These compare the same model family through different endpoints and prompts;
they are consistency diagnostics, not independent human accuracy.

## Concrete inspected differences

| Original review ID | Difference | Assistant inspection |
|---|---|---|
| 84e0871d-85b8-45f1-93c1-a95ad1dd0f45 | General praise: enrichment other, verifier catalog | “Love playing my favorites” is not clearly a catalog problem. Keep the uncertainty visible; verifier is not ground truth. |
| 9ae47fdd-c9a3-44b9-8d63-2a067cc92191 | “Resend update very worst”: enrichment severity 2, verifier 1 | The shared rubric assigns generic criticism severity 2. The verifier's 1 is a likely error. |
| 10042129-73f0-42ba-8fdf-df397d5f097e | Sarcastic rating/ad wording: enrichment other/unclear, verifier catalog/complaint | Wording is ambiguous; catalog is weakly supported. A person should inspect the original text before treating the verifier as a correction. |
| 9453c7f9-907a-4af8-b3a1-9d7b7430d31f | Explicit paid shuffle restriction: enrichment billing/cancellation/3, verifier usability/cancellation/2 | The explicit paywall supports billing; restricted function supports severity 3. The enrichment appears more consistent with the rubric. |
| 0c45597c-1915-42b6-8ca7-145c1fd415fa | Premium-only song restrictions: billing/complaint/2 versus usability/complaint/3 | The topic boundary supports billing. Severity depends on whether the author reports their own restricted task or criticizes others' restrictions; retain that ambiguity. |

No business labels were silently replaced with verifier answers. Full original
text and both predictions for all 100 comparisons are in verification_review.json.
The existing 50-human-label evaluation is preserved and applies to the unchanged
Responses enrichment configuration. No fresh independent human evaluation of
the Decisions verifier has been performed.

## Actual execution failures and repairs

- Source preparation initially used a slow indexed SQLite sort. It was interrupted
  before any model calls and replaced with streaming the checksum-validated source CSV.
- Eight Decisions requests returned HTTP 400 `array_above_max_length`. Those first
  errors recorded the code but not the rejected parameter, so the precise endpoint
  array maximum is unknown. The repaired verifier uses two reviews per request,
  ten questions and five sentiment levels. All 100 independent predictions then
  succeeded. Original requests, failed calls, reservations and configuration are saved.
- One memo response had no usable structured output. The allowed invalid-output
  retry succeeded. Both attempts and their actual usage remain included.
- No completed enrichment ID was relabeled during verification repair. The cold
  measurement includes active failed-request/repair execution, while preparation,
  process startup, development and approval waiting are excluded.

The instructor checker reports only 16 missing token fields on the eight rejected
requests. Their US$0.04533560 reservations remain unresolved, separate from
US$0.041287690 of known pilot usage. The processing/scaling checks pass; billing
reconciliation is still incomplete. This is not a fully reconciled checker pass.
