"""Read-only, signed-out verification of the submitted Vercel/Neon deployment."""
import json
import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import csv_rows, now, read_json, row_sha, write_json

BASE = "https://spotify-review-evidence-100k.vercel.app"


def request(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed',action='store_true')
    args=parser.parse_args()
    root=Path('artifacts/runs/production-100k-v1')
    revision=root/'revisions/submission-review-v1'
    verification=read_json(revision/'verification_reviewed.json') if args.reviewed and (revision/'verification_reviewed.json').exists() else read_json(root/'verification.json')
    complete=len(verification['predictions']);partial=len(verification.get('refusals',[]))
    health_status, health = request("/api/health")
    assert health_status == 200 and health["database"] == "connected"
    status, summary = request("/api/summary")
    saved = read_json("artifacts/runs/production-100k-v1/summary.json")
    assert status == 200 and summary["status"] == "completed"
    assert summary["completed"] == saved["completed"] == 100000
    assert summary["verified"] == 5000
    assert summary["quality"]["complete_prediction_count"] == complete
    assert summary["quality"]["refusal_count"] == partial
    if args.reviewed:
        assert summary['reviewed_memo'] is True and summary['reviewed_verification'] is True
        golden=read_json('evals/production_golden/acceptance.json')
        assert summary['quality']['production_golden']['agreement']==golden['agreement']
        assert summary['quality']['production_golden']['original_human_labels_sha256']==golden['original_human_labels_sha256']
    local_ranking = list(csv_rows("artifacts/runs/production-100k-v1/ranking.csv"))
    for remote, local in zip(summary["ranking"], local_ranking, strict=True):
        for key in local:
            assert str(remote[key]) == local[key], (key, remote, local)
    local_memo = read_json(revision/'memo.json' if args.reviewed else root/'memo.json')
    assert summary["memo"] == local_memo
    local_claims = list(csv_rows("artifacts/runs/production-100k-v1/claims.csv"))
    assert summary["claims"] == local_claims
    pages = []
    for number in [1, 2]:
        code, page = request(f"/api/reviews?page={number}")
        assert code == 200 and len(page["rows"]) == 20
        pages.extend(page["rows"])
    assert len({r["id"] for r in pages}) == 40
    for row in pages:
        assert row["body"] == row["source"]["review_text"]
        assert row["source_hash"] == row_sha(row["source"])
        assert row["evidence"] in row["body"]
    code, filtered = request("/api/reviews?topic=playback&intent=friction")
    assert code == 200 and filtered["rows"]
    assert all(r["topic"] == "playback" and r["intent"] in {"complaint", "cancellation"} for r in filtered["rows"])
    assert request("/api/reviews?topic=foreign")[0] == 400
    query = urllib.parse.quote("%_' OR 1=1 -- invalid-label-test")
    assert request("/api/reviews?q=" + query)[1]["total"] == 0
    assert request("/api/import", "POST", b"{}")[0] == 401
    report = {"saved_at": now(), "url": BASE, "passed": True,
        "signed_out_public_access": True, "database_connected": True,
        "completed_reviews": 100000, "verification_outcomes": 5000,
        "complete_verifier_predictions": complete, "partial_refusals": partial,"reviewed_memo":args.reviewed,
        "rankings_memo_claims_equal_saved_files": True,
        "pagination_unique": True, "source_hashes_and_quotes_valid": True,
        "filters_valid": True, "invalid_filter_rejected": True,
        "literal_sql_injection_search": True, "unauthorized_import_rejected": True,
        "model_calls": 0}
    if args.reviewed:
        report['final_configuration_human_agreement']=summary['quality']['production_golden']['agreement']
    write_json("evals/dashboard/vercel_live_e2e.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
