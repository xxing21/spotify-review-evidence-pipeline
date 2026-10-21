# Human review comparison — 50 reference reviews

All 50 human cases are saved and valid. The AI produced 50 valid predictions, including one exact-text cache alias, only after human labeling finished. Your answers remain unchanged.

| Field | Matched human choice | Agreement |
|---|---:|---:|
| topic | 41/50 | 82% |
| intent | 44/50 | 88% |
| severity | 33/50 | 66% |

Severity differs on 17 cases: AI higher on 15 and lower on 2. The average absolute difference is 0.40 on the 1–5 scale. Sentiment average absolute difference is 0.238 on the -1 to +1 scale.

Eight human cases are marked ambiguous. The small sample contains 32 other, 10 usability, 5 playback, 2 catalog and 1 support reference labels. Access, billing and downloads have no human-reference cases, limiting category coverage. These are agreements with your judgments, not independently adjudicated population accuracy.

All model and human quotes are literal source substrings; all entity entries are literal source mentions. Exact quote wording agrees on 20% because the model stores whole reviews and human quotes can be shorter. This does not imply invalid quotes. Entity-list exact agreement is 60%; semantic usefulness and completeness require inspection.

## Recommended review

Review the 17 severity disagreements against the shared rubric before the full run. Several general complaints are human severity 1 and AI severity 2; the rubric assigns general criticism without functional loss to 2. Either judgment may need review; no human answer or model prediction was automatically changed.

- Review 4: limited functionality; human severity 2, AI 3. Clarify annoyance versus restricted function.
- Review 6: generic criticism; human severity 1, AI 2. Reconcile the no-problem versus annoyance boundary.
- Review 30: basic features described as Premium; human topic other, AI billing. Apply the explicit paywall rule.
- Review 12: an update says support fixed the issue, while an old crash complaint remains. Human support/praise/1 versus AI playback/complaint/4. Clarify resolved updates and historical complaints.

Preserve the original answers and record adjudications separately. If golden findings inform prompt tuning, disclose that use and collect fresh held-out human cases before claiming an independent final evaluation. No prompts have been changed in response to these results.

## Case-by-case core disagreements

| Review | ID | Human topic / intent / severity | AI topic / intent / severity |
|---:|---|---|---|
| 1 | 292ce26a-815d-4bce-a3b6-93cb6c9e7e2c | other / complaint / 2 | catalog / complaint / 3 |
| 4 | 991b6b3a-f511-458a-a5b7-234f78048fb5 | usability / complaint / 2 | usability / complaint / 3 |
| 6 | 0c6ca545-3f89-4da6-b3db-1a352371fb6e | other / complaint / 1 | other / complaint / 2 |
| 12 | 723f07de-9881-4049-8680-1a9e25652914 | support / praise / 1 | playback / complaint / 4 |
| 13 | 47428620-ec21-424d-a515-0b0b0012a5cf | other / complaint / 1 | other / complaint / 2 |
| 19 | 46842184-32f8-4088-ac15-2a700a7e94ed | other / unclear / 1 | catalog / complaint / 3 |
| 20 | 657f1b77-0183-4b06-bf48-5e6d9ab08f9a | other / complaint / 1 | other / complaint / 2 |
| 24 | 372d4e67-59cc-4c54-879f-3e8a202ee554 | usability / complaint / 1 | usability / complaint / 2 |
| 25 | 47f1406d-4918-4d60-9647-5ca8e610caca | playback / complaint / 3 | playback / complaint / 4 |
| 29 | 3ddb3f4e-f7b9-430b-b335-eadc6d321f46 | usability / complaint / 4 | usability / cancellation / 3 |
| 30 | 16d640e9-b281-4746-9562-c7dbcf7126b6 | other / complaint / 2 | billing / complaint / 3 |
| 31 | 8cc4fad4-26ec-47b7-96e8-49c7da714eca | other / unclear / 1 | other / complaint / 2 |
| 37 | 2aa566c6-b98d-4513-b900-83702a8db8eb | other / praise / 1 | usability / praise / 1 |
| 38 | 8c0546b0-ce43-4a36-9d33-9f979e98d522 | playback / complaint / 3 | catalog / complaint / 3 |
| 41 | b58dd6f0-ad88-4319-b6db-58afb60c37c1 | usability / complaint / 2 | usability / request / 1 |
| 42 | 1a41c7e1-a655-4c63-b4db-c22bdff18003 | other / complaint / 1 | other / complaint / 2 |
| 43 | dceb14e7-2df0-422f-bb2b-73d7c373159a | usability / complaint / 4 | playback / complaint / 4 |
| 45 | ac4e860a-c042-49cc-90f3-189591c336ac | playback / complaint / 3 | downloads / complaint / 4 |
| 46 | 9034d675-9582-49b6-a1c1-c4ddabf8baf1 | usability / complaint / 1 | usability / complaint / 2 |
| 47 | d2f3874f-d15d-4a2f-bb97-4f1213defa46 | usability / complaint / 2 | usability / complaint / 3 |
| 48 | 99b93e31-9f15-4daa-88ac-349ab0419c48 | other / complaint / 1 | usability / request / 1 |

Evaluation cost: US$0.002421625, within the shared US$2 cap. Offline replay makes zero model calls.

Files: golden_labels.json (human), golden_report.json (complete comparisons), golden_predictions.jsonl (AI only), golden_validation.json (separation and replay evidence).

Offline replay: `python3 -m spotify_pipeline evaluate --run-id pilot-10000-v3`
