# Source-to-claim trace — actual pilot evidence

Review ID: `41c0c736-6617-466a-8e4d-3a2b551185e5`
Source row hash: `aea52421929f91c6f181280a2504bd4be8ba2859205d5001ee881a56e0a9e455`

Enrichment: billing / complaint / severity 5.
Independent verifier: {"entities": ["Spotify"], "evidence_quote": "I had unsubscribed, and Spotify stole My money!!!", "intent": "complaint", "needs_review": true, "review_id": "41c0c736-6617-466a-8e4d-3a2b551185e5", "sentiment": -1, "severity": 5, "topic": "billing"}
Membership: `ISSUE-BILLING`; see membership.csv and ranking.csv.
Memo claim references: ISSUE-BILLING-complaint_count, ISSUE-BILLING-severity_sum, ISSUE-BILLING-mean_severity

Exact quote: "I had unsubscribed, and Spotify stole My money!!!"

## Failure/ambiguity handling

{
  "entities": [],
  "evidence_quote": "Maja nahi aya",
  "intent": "unclear",
  "label_config": "gpt-6-luna:e5b9ca8a9f0fea04604aede9424ae0bb95e897bc99732d0db7aef7083c184699",
  "needs_review": true,
  "review_id": "000b587e-b833-476b-8063-801f4ef36672",
  "sentiment": -0.5,
  "severity": 1,
  "source_sha256": "037ca3ca8bdf3b71a6af43509ec7a468cba146182c00c090a05aa150da000c18",
  "status": "completed",
  "topic": "other"
}

Ambiguous cases are retained with needs_review and are not silently excluded from business counts.
All failed provider attempts remain in calls.jsonl; unknown charges keep reservations.
Human inspection of label correctness and the final argument remains pending.
