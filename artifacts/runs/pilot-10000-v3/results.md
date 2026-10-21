# Results of the 10,000-review checkpoint

10,000 of 10,000 original reviews completed. The 500 earlier results were reused; 7,970 new model classifications were saved, with reuse keyed by exact text and schema settings.

Additional API usage cost: US$0.4785. Measured incremental time: 115.8 minutes, including restart and analysis. Repeating the completed workflow made 0 new API calls.

15 failed requests returned no usage details. US$0.049552 remains reserved as possible additional charges. The instructor checker marks billing usage for review; all record, cache, source-hash and ranking checks pass. No missing usage was replaced with zero.

Intent counts: cancellation: 400, complaint: 3,855, praise: 4,255, request: 345, unclear: 1,145.

| Rank | Issue | Complaint/cancellation reviews | Priority score |
|---|---|---:|---:|
| 1 | Controls, navigation and ads | 1358 | 3504 |
| 2 | Playback, crashes and loading | 661 | 2149 |
| 3 | General dissatisfaction | 1010 | 1991 |
| 4 | Billing and Premium restrictions | 647 | 1833 |
| 5 | Content, search and recommendations | 304 | 885 |
| 6 | Login and account access | 163 | 617 |
| 7 | Downloads and offline listening | 103 | 335 |
| 8 | Support | 9 | 25 |

The priority score is the sum of seriousness scores. Each complaint or cancellation belongs to exactly one issue.

Independent checking covered 2,000 reviews. It disagreed on topic, intent or seriousness for 397; 1,280 differed in any field. These compare two AI judgments and do not measure accuracy against human truth.

2,362 reviews are flagged for inspection and remain in the totals. All 50 human reference labels are now complete. AI agreement is 82% for topic, 88% for intent and 66% for severity. See evals/golden_results.md for disagreements requiring review.

Premium restrictions and control complaints remain a known topic boundary to inspect. The recommendation in memo.md is provisional; its numbers and references resolve to claims.csv and source evidence.

Recommendation: investigate controls and unwanted background playback, with playback reliability as the strongest alternative. The controls/navigation total covers the entire usability category, including ads and layout. Split that category and review Premium-related labels before committing to a product investment.

This checkpoint stops at 10,000 classified reviews. Full-file ingestion is separate; no full classification or deployment is claimed.
