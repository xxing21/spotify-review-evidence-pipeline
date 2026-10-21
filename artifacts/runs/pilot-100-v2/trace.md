# Source-to-claim trace — actual pilot evidence

Review ID: `66a29b3c-c14d-440e-b722-b23e0c99ae82`
Source row hash: `f84ca949889d90597732f573c8b031805f95a1e20ad62d1fe4f29b3162579878`

Enrichment: playback / complaint / severity 4.
Independent verifier: {"entities": [], "evidence_quote": "App is stuck on loading/logo screen", "intent": "complaint", "needs_review": false, "review_id": "66a29b3c-c14d-440e-b722-b23e0c99ae82", "sentiment": -0.7, "severity": 4, "topic": "playback"}
Membership: `ISSUE-PLAYBACK`; see membership.csv and ranking.csv.
Memo claim references: ISSUE-PLAYBACK-complaint_count, ISSUE-PLAYBACK-severity_sum, ISSUE-PLAYBACK-priority_score

Exact quote: "App is stuck on loading/logo screen"

## Failure/ambiguity handling

{
  "entities": [],
  "evidence_quote": "Worst app",
  "intent": "complaint",
  "label_config": "gpt-6-luna:cd2a0784dfc7d34dc083a289aada06e76b1524c8a9d15961199e68252797985f",
  "needs_review": true,
  "review_id": "06a45bd5-3ed9-43af-b7f2-8b9487e2ffff",
  "sentiment": -0.8,
  "severity": 2,
  "source_sha256": "8a9a7dba61eacf44f1a55829f9459fd5253eabc149f8094719339531a311c0d4",
  "status": "completed",
  "topic": "other"
}

Ambiguous cases are retained with needs_review and are not silently excluded from business counts.
All failed provider attempts remain in calls.jsonl; unknown charges keep reservations.
Human inspection of label correctness and the final argument remains pending.
