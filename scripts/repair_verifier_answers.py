"""One explicitly authorized final attempt for the original two verifier refusals."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import LABEL_FIELDS,LABEL_SCHEMA,csv_rows,ground_labels,now,read_json,read_jsonl,sha,write_json
from spotify_pipeline.provider import ModelClient
from spotify_pipeline.store import Store,experiment_lock


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute-paid',action='store_true')
    p.add_argument('--allow-final-invalid-attempt',action='store_true')
    a=p.parse_args()
    if a.execute_paid and not a.allow_final_invalid_attempt:
        p.error('The original invalid-output retry was exhausted; --allow-final-invalid-attempt is required')
    root=Path('artifacts/runs/production-100k-v1')
    out=root/'revisions/submission-review-v1'
    original=read_json(root/'verification.json');refused=original['refusals']
    ids=[r['review_id'] for r in refused]
    fixed={'a3480188-eba3-4f97-bcf5-280691f7ed43','537ae160-c12d-45c5-bc6a-f157c094e626'}
    if set(ids)!=fixed or len(ids)!=2:raise ValueError('Repair is bound to the original two refused source IDs')
    indexed={r['review_id']:r for r in csv_rows(root/'input_100000.csv') if r['review_id'] in fixed}
    rows=[indexed[rid] for rid in ids]
    plan={'prepared_at':now(),'run_id':'verification-final-repair-v1','source_run':'production-100k-v1',
        'review_ids':ids,'prior_attempts_per_review':2,'maximum_additional_attempts_per_review':1,
        'original_verification_sha256':sha(root/'verification.json'),'repair_cap_usd':'.01','shared_cap_usd':'10',
        'new_calls':0,'status':'prepared','sample_unchanged':True,'enrichment_predictions_sent':False}
    if not a.execute_paid:
        write_json(out/'verification_repair_plan.json',plan);print(json.dumps(plan,indent=2));return
    state=Store()
    try:
        cfg=state.run('production-100k-v1')['config']|{'max_task_attempts':1,'prior_verification_attempts':{rid:2 for rid in ids}}
        for item in refused:
            if len(item['source_call_ids'])!=2:raise ValueError('Original attempt provenance changed')
            for cid in item['source_call_ids']:
                event=state.db.execute('SELECT event FROM calls WHERE id=?',(cid,)).fetchone()
                event=json.loads(event[0]) if event else {}
                if event.get('error_kind')!='invalid_output' or item['review_id'] not in event.get('review_ids',[]):
                    raise ValueError('Original invalid-output pair does not match repair provenance')
        run_id=plan['run_id'];directory=Path('artifacts/evaluation')/run_id
        with experiment_lock(Path('state/paid-command')):
            state.new_run(run_id,state.run('production-100k-v1')['dataset'],cfg,{'kind':'verification_repair','scope':'original two refused IDs only'})
            before=len(state.calls(run_id));client=ModelClient(state,run_id,cfg,10,directory,run_cap=Decimal('.01'))
            try:
                answer=client.call('verify',{'reviews':[{'review_id':r['review_id'],'review_text':r['review_text']} for r in rows]},
                    LABEL_SCHEMA,lambda x:ground_labels(x,rows),'final_authorized_repair',review_ids=ids)
                result=plan|{'status':'completed','predictions':answer['records']}
                full={r['review_id']:r for r in original['predictions']+answer['records']}
                if len(full)!=5000 or set(full)!=set(original['sample_ids']):raise ValueError('Reviewed sample coverage differs')
                reviewed=original|{'predictions':[full[rid] for rid in original['sample_ids']],
                    'refusals':[],'original_refusals_preserved':refused,'supplemental_run':run_id}
                enriched={r['review_id']:r for r in read_jsonl(root/'records.jsonl')}
                reviewed['comparisons']=[{'review_id':rid,'missing_enrichment':False,
                    'different_fields':[k for k in LABEL_FIELDS if full[rid][k]!=enriched[rid][k]]} for rid in original['sample_ids']]
                reviewed['label_disagreements']=sum(any(k in c['different_fields'] for k in ('topic','intent','severity')) for c in reviewed['comparisons'])
                reviewed['any_field_disagreements']=sum(bool(c['different_fields']) for c in reviewed['comparisons'])
                write_json(out/'verification_reviewed.json',reviewed)
            except (ValueError,RuntimeError,TimeoutError) as error:
                result=plan|{'status':'incomplete','error':str(error),'original_partial_answers_retained':True}
            calls=state.calls(run_id)
            result.update(saved_at=now(),new_calls=len(calls)-before,attempt_call_ids=[c['local_call_id'] for c in calls],
                all_work_spent_plus_reserved_usd=str(state.committed_spend()))
            write_json(out/'verification_repair_result.json',result)
            write_json(directory/'calls.json',calls)
            write_json('cost/budget_ledger.json',{'cap_usd':10,'spent_plus_unresolved_reservations_usd':str(state.committed_spend()),
                'scope':'All experiments and production, including unresolved reservations'})
            print(json.dumps(result,indent=2))
            if result['status']!='completed':raise SystemExit(1)
    finally:state.close()


if __name__=='__main__':main()
