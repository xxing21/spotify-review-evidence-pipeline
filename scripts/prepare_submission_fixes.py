"""Prepare a reviewable memo correction and honest missing-usage inventory. Offline only."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import csv_rows, now, read_json, read_jsonl, sha, write_json, atomic_text
from spotify_pipeline.pipeline import validate_memo


def main():
    run=Path('artifacts/runs/production-100k-v1')
    out=run/'revisions/submission-review-v1'
    original=read_json(run/'memo.json')
    revised=dict(original)
    revised['rationale']=original['rationale'].replace(
        'Playback is a strong alternative: it has higher mean severity and reports include playback disruption and device instability.',
        'Playback is a strong alternative: it has higher mean severity and reports describe historical playback disruption and device instability. The cited crash report was later updated to say the problem was fixed, so it supports historical experience rather than an unresolved defect.')
    if revised['rationale']==original['rationale']:
        raise ValueError('Original memo changed; review the proposed correction before applying it')
    revised['limitations']=original['limitations'].replace('This is a bounded pilot, not a full-corpus conclusion.',
        'This recommendation covers the selected review sample and historical experiences. Current relevance requires validation.')
    validate_memo(revised,list(csv_rows(run/'ranking.csv')),list(csv_rows(run/'claims.csv')),read_json(run/'evidence.json'))
    write_json(out/'memo.json',revised)
    text=(run/'memo.md').read_text()
    text=text.replace(original['rationale'],revised['rationale']).replace(original['limitations'],revised['limitations'])
    text+='\nReview revision: assistant clarification of the original generated memo; no new model call, label change, ranking change or numerical claim. The original memo is preserved in the parent run directory.\n'
    atomic_text(out/'memo.md',text)
    missing=[]
    for c in read_jsonl(run/'calls.jsonl'):
        if c.get('calculated_api_usd') is not None:continue
        handoff=read_json(run/'handoffs'/(c['local_call_id']+'.json'))
        raw=handoff.get('response') or {}
        missing.append({k:c.get(k) for k in ['local_call_id','started_at','ended_at','role','attempt','error_kind','provider_request_id','reservation_usd']}|
            {'provider_response_id':raw.get('id'),'saved_usage':raw.get('usage'),'response_storage_requested':handoff['request'].get('store')})
    inventory={'checked_at':now(),'status':'unresolved_from_available_evidence','missing_usage_calls':len(missing),
        'unresolved_reserved_usd':str(sum((Decimal(c['reservation_usd']) for c in missing),Decimal(0))),
        'recoverable_provider_response_ids':sum(bool(c['provider_response_id']) for c in missing),
        'provider_request_ids':sum(bool(c['provider_request_id']) for c in missing),
        'per_request_usage_not_inferred_from_aggregate_bill':True,'charges_not_assumed_zero':True,
        'historical_attempts_unchanged':True,'new_model_calls':0,'calls':missing,
        'official_cost_documentation':'https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs',
        'reconciliation_limit':'Organization costs are aggregated. They do not establish exact input/output token counts for each failed request. A separately authorized account export or provider evidence may reconcile aggregate charges; absent request-level evidence, usage remains unavailable and reservations remain.'}
    write_json('evals/production_100k/usage_reconciliation.json',inventory)
    proof={'prepared_at':now(),'status':'prepared_not_published','original_memo_sha256':sha(run/'memo.json'),
        'reviewed_memo_sha256':sha(out/'memo.json'),'reviewed_memo_path':str(out/'memo.json'),
        'records_sha256':sha(run/'records.jsonl'),'ranking_sha256':sha(run/'ranking.csv'),
        'claims_sha256':sha(run/'claims.csv'),'source_reviews_unchanged':True,'classification_changes':0,
        'claims_unchanged':True,'new_model_calls':0,'original_memo_preserved':True}
    write_json(out/'review.json',proof)
    print(json.dumps(proof,indent=2))


if __name__=='__main__':main()
