# Source-to-claim trace — actual pilot evidence

Review ID: `16929558-ce1e-4b87-8738-a1de3f557f66`
Source row hash: `d5b748cfaf8d9d9980825fbcad7dfd54c1141185b60c59733b701ac81359b73c`

Enrichment: billing / complaint / severity 4.
Independent verifier: {"entities": [], "evidence_quote": "I paid my subscription and im still getting a pause subscription screen and can't access my music...... help me", "intent": "complaint", "needs_review": false, "review_id": "16929558-ce1e-4b87-8738-a1de3f557f66", "sentiment": -0.8, "severity": 4, "topic": "billing"}
Membership: `ISSUE-BILLING`; see membership.csv and ranking.csv.
Memo claim references: ISSUE-BILLING-complaint_count, ISSUE-BILLING-priority_score, ISSUE-BILLING-mean_severity

Exact quote: "I paid my subscription and im still getting a pause subscription screen and can't access my music...... help me"

## Failure/ambiguity handling

{
  "entities": [],
  "evidence_quote": "Worst",
  "intent": "unclear",
  "label_config": "gpt-6-luna:cd2a0784dfc7d34dc083a289aada06e76b1524c8a9d15961199e68252797985f",
  "needs_review": true,
  "review_id": "00363dc8-2117-4565-9af9-efadf8fa90cf",
  "sentiment": -0.8,
  "severity": 2,
  "source_sha256": "15ba615612ad7a1e015f2f36ee1df1bc97ef50522006f1e0efe44cc433b92da7",
  "status": "completed",
  "topic": "other"
}

Ambiguous cases are retained with needs_review and are not silently excluded from business counts.
All failed provider attempts remain in calls.jsonl; unknown charges keep reservations.
Human inspection of label correctness and the final argument remains pending.
