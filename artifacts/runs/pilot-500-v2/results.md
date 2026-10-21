# Results of the 500-review pilot

All 500 reviews were processed successfully. We reused the original 100 results,
so the additional work covered 400 more reviews. Repeated text reduced the number
of new AI classifications to 379. No reviews were quarantined.

The additional work took about six and a half minutes and cost an estimated
US$0.0232 in recorded AI usage. Repeating it used no new AI calls.

Of the 500 reviews, 216 were positive, 207 reported complaints, 25 expressed an
intention to leave or cancel, 10 requested improvements, and 42 were unclear.
An intention to leave is not proof that the customer actually left.

The complaint/cancellation ranking combines frequency and seriousness:

| Rank | Issue | Reviews | Priority score |
|---|---|---:|---:|
| 1 | Controls, navigation and ads | 76 | 201 |
| 2 | Playback, crashes and loading | 43 | 142 |
| 3 | Billing and Premium restrictions | 32 | 95 |
| 4 | General dissatisfaction | 44 | 86 |
| 5 | Content, search and recommendations | 20 | 55 |
| 6 | Login and account access | 8 | 30 |
| 7 | Downloads and offline listening | 8 | 28 |
| 8 | Support | 1 | 2 |

These numbers correspond to each issue's complaint_count and priority_score
claim IDs in claims.csv; issue IDs are ISSUE-USABILITY, ISSUE-PLAYBACK,
ISSUE-BILLING, ISSUE-OTHER, ISSUE-CATALOG, ISSUE-ACCESS, ISSUE-DOWNLOADS and
ISSUE-SUPPORT respectively. The table covers 232 complaint/cancellation records.

The preliminary recommendation is to investigate listening controls and free-tier
restrictions, with playback reliability as the strongest alternative. Billing
and subscription-access problems also merit attention.

The independent check disagreed on topic, intent or seriousness for 18 of 100
sampled reviews. Some Premium restrictions likely belong under billing rather
than usability, so the ranking can change after human review. The recommendation
is a working hypothesis, not a final Spotify investment decision.

See memo.md, memo_review.md, claims.csv and self-check.json in this directory.
The 50 human labels are still pending. No larger run or deployment has started.
