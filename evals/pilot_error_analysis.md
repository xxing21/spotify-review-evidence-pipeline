# Pilot development failures and label limitations

This analysis uses development reviews only. It is assistant inspection, not the
required human golden labeling. Original model predictions remain unchanged.

## Actual execution failures

- Initial model access was valid, but generation returned HTTP 429 on all three
  allowed attempts. Usage was unavailable; US$0.009600 remains conservatively
  reserved. The user corrected account access. The original attempts are retained.
- The first language experiment (`pilot-100`) completed 60 records and quarantined
  40 after output-validation failures. It imposed exact literal entity extraction
  on the model, so capitalization differences caused entire batches to fail.
  Raw requests, responses, usage and retries remain in its handoffs and archived
  cost evidence. This is an inspected implementation failure, not discarded data.
- Version two changes the prompts and extraction policy: code supplies literal
  quotes and explicit entity spans. Its fresh-cache experiment completed all
  100 records without enrichment retries or quarantines.
- Version two's memo initially included disallowed numerical prose. The validator
  rejected it, saved usage/charge evidence, and the single allowed retry succeeded.
  This is a real retry demonstration in addition to synthetic-provider tests.

## Independent verification

The declared random sample contains 20 original IDs. Topic/intent/severity differ
on 5 cases; at least one field differs on 12. Sentiment differences account for
many of the extra disagreements. Quotes and entities are grounded by code, so their
agreement is deterministic and does not demonstrate semantic accuracy.

| Development review ID | Observed disagreement | Inspection |
|---|---|---|
| b39971d2-e3f0-4559-96da-a609f54d9cb4 | General praise: other vs playback | “Best for listening songs” leaves the specificity of the praised feature debatable. |
| ed15bb17-865a-492b-ba1b-268f4cab78f6 | Mixed-language praise: other vs usability | Both flagged needs_review; bilingual human review is needed. |
| b92a7381-b5cd-4c77-9176-e5c4b4818c8a | complaint/severity 2 vs unclear/severity 1 | “You deserve 0 star” is generic negative criticism; the shared rubric supports complaint without inferring a defect. |
| cf6166ae-d71a-4839-9add-088645ad3b78 | usability/cancellation vs playback/complaint | The text warns others not to download and reports ads. A warning is not explicit personal departure; inspect complaint/usability. |
| 618d1dbb-0186-4537-923a-7b4dabf19afb | usability vs catalog | Unwanted recommendations in a playlist sit near a topic boundary; the explicit threat to switch supports cancellation. |

## Material memo limitation: usability vs billing

The top issue is usability under the saved labels. However, its cited reviews
`88439ec2-7c49-4c57-bedb-c5e098692aff` and
`a78d831a-69f4-428a-9235-cfdd9775c509` explicitly connect restricted controls to
buying Premium. The contract assigns explicitly Premium-only controls to billing.
These are likely topic errors requiring human review. They may change issue
membership, ranking and the recommendation. The AI memo is a provisional argument
over saved pilot labels, not a validated product investment decision.

`06a45bd5-3ed9-43af-b7f2-8b9487e2ffff` (“Worst app”) is retained as
other/complaint/severity 2 with needs_review=true. Generic criticism provides no
specific defect. Flagged records remain in the analysis and are not dropped to
improve agreement.

## Real synthetic-input model tests

The separate paid diagnostics passed: injected instructions did not change the
playback complaint to the demanded billing/praise label; the verifier re-labeled
the planted access example independently and disagreed with all deliberately
wrong topic/intent/severity fields. These synthetic inputs are excluded from
business membership, ranking and the 100-review measurement. See
`cost/diagnostics.json` and `cost/diagnostics_calls.jsonl`.

## Before scaling

Complete the 50 human labels blindly, inspect the full golden comparison and
quote support, and decide whether development-only prompt examples or a capped
fallback improve the topic boundaries. If golden results guide changes, disclose
that and add fresh held-out cases. Do not claim population accuracy from this
small sample or call verifier agreement a correctness guarantee.
