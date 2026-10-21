"""Audit actual 100k outputs and create an honest full-file accounting export. No model calls."""
import collections
import gzip
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from check_submission import audit, reference, reference_hash
from spotify_pipeline.common import (LABEL_FIELDS, canonical, csv_rows, now, read_json, read_jsonl,
    row_sha, sha, validate_labels, write_csv, write_json)
from spotify_pipeline.pipeline import rerank_exports, validate_memo
from spotify_pipeline.production import verification_rows
from spotify_pipeline.production_cost import compute, replay
from spotify_pipeline.store import Store


def main():
    directory=Path('artifacts/runs/production-100k-v1');evaluation=Path('evals/production_100k');evaluation.mkdir(parents=True,exist_ok=True)
    summary=read_json(directory/'summary.json')
    if summary['status']!='completed' or summary['completed']!=100000:
        raise ValueError('100k is not completed; no successful milestone or final submission claimed')
    source=list(csv_rows(directory/'input_100000.csv'));by_source={r['review_id']:r for r in source}
    records=read_jsonl(directory/'records.jsonl');indexed={r['review_id']:r for r in records}
    if len(records)!=100000 or len(indexed)!=100000 or set(indexed)!=set(by_source):
        raise ValueError('Missing, duplicate or foreign completed source IDs')
    for record in records:
        validate_labels({'records':[{k:record[k] for k in ('review_id',*LABEL_FIELDS)}]},[by_source[record['review_id']]])
        if record['source_sha256']!=row_sha(by_source[record['review_id']]):raise ValueError('Source hash mismatch')
    ref=reference('spotify_reviews_18months.csv',directory/'input_100000.csv')
    checked=audit(directory/'grading',ref,ref_digest=reference_hash(ref))
    write_json(directory/'self-check.json',checked)
    verified=read_json(directory/'verification.json')
    expected=verification_rows(source,summary['config'])
    complete_count=len(verified['predictions'])
    sample_ok=verified['sample_ids']==[r['review_id'] for r in expected] and complete_count+len(verified.get('refusals',[]))==5000
    source_only=True
    for path in (directory/'handoffs').glob('*.json'):
        handoff=read_json(path)
        if handoff['attempt']['role'] in {'enrich','verify'}:
            data=json.loads(handoff['request']['input'][1]['content'])
            source_only &= set(data)=={'reviews'} and all(set(r)=={'review_id','review_text'} and by_source[r['review_id']]['review_text']==r['review_text'] for r in data['reviews'])
    calls=read_jsonl(directory/'calls.jsonl')
    counts=collections.Counter((c['role'],rid) for c in calls for rid in c['review_ids'])
    quality={'sample_count':5000,'complete_prediction_count':complete_count,'refusal_count':len(verified.get('refusals',[])),
        'metric_denominator':complete_count,'method':'Independent original-text/rubric GPT Decisions; same Luna model family, not human truth; complete-prediction denominators exclude explicit partial refusals',
        'core_label_disagreements':verified['label_disagreements'],
        'agreement':{k:sum(p[k]==indexed[p['review_id']][k] for p in verified['predictions'])/complete_count for k in LABEL_FIELDS},
        'severity_mae':sum(abs(p['severity']-indexed[p['review_id']]['severity']) for p in verified['predictions'])/complete_count,
        'sentiment_mae':sum(abs(p['sentiment']-indexed[p['review_id']]['sentiment']) for p in verified['predictions'])/complete_count}
    write_json(evaluation/'verification_quality.json',quality)
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for name in ['records.jsonl','membership.csv','ranking.csv','claims.csv']:shutil.copy2(directory/name,tmp/name)
        before=(tmp/'ranking.csv').read_bytes();rerank_exports(tmp);ranking_same=before==(tmp/'ranking.csv').read_bytes()
        rate_rows=list(csv_rows('cost/rates.csv'))
        for row in rate_rows:row['price_per_unit']=str(Decimal(row['price_per_unit'])*2)
        double=tmp/'rates.csv';write_csv(double,rate_rows,list(rate_rows[0]))
        shutil.copy2('cost/rates.csv','cost/production_100k/rates.csv')
        base,_=compute();doubled,_=compute(rates_path=double);volume,_=compute(volume=100000)
        rates_ok=Decimal(doubled['measured']['known_api_usd'])==2*Decimal(base['measured']['known_api_usd'])
        time_ok=doubled['measured']['active_seconds']==base['measured']['active_seconds']
        volume_ok=volume['measured']==base['measured']
    replay()
    validate_memo(read_json(directory/'memo.json'),list(csv_rows(directory/'ranking.csv')),list(csv_rows(directory/'claims.csv')),read_json(directory/'evidence.json'))
    # Keep the scoped grading adapter unchanged. The final adapter accounts for every original source ID.
    full=Path('submission/grading');full.mkdir(parents=True,exist_ok=True)
    for name in ['ingestion.json','membership.csv','ranking.csv','claims.csv','checkpoint_before.json','checkpoint_after.json']:
        shutil.copy2(directory/'grading'/name,full/name)
    with gzip.open(full/'records.jsonl.gz','wt',encoding='utf-8',newline='') as out:
        for row in csv_rows('spotify_reviews_18months.csv'):
            record=indexed.get(row['review_id'])
            if record is None:
                record={'review_id':row['review_id'],'source_sha256':row_sha(row),'status':'quarantined',
                    'reason':'empty_review_text' if not row['review_text'].strip() else 'outside_100k_analysis_scope','attempt_count':0}
            out.write(canonical(record)+'\n')
    with gzip.open(full/'calls.jsonl.gz','wt',encoding='utf-8',newline='') as out:
        for call in calls:out.write(canonical(call)+'\n')
    write_json(full/'run.json',{'version':'a5-audit-v1','analysis_count':660622,'analysis_sha256':sha('spotify_reviews_18months.csv'),
        'classification_input_fields':['review_text'],'allow_multi_issue':False,'run_id':summary['run_id'],
        'scope':'100000 nonempty original IDs classified; 13 empty texts quarantined; remaining 560609 explicitly excluded from this 100k analysis, not classified'})
    fullref=reference('spotify_reviews_18months.csv','spotify_reviews_18months.csv')
    fullcheck=audit(full,fullref,ref_digest=reference_hash(fullref))
    write_json(evaluation/'full_file_self_check.json',fullcheck)
    store=Store()
    try:global_amount=store.committed_spend()
    finally:store.close()
    outcome={'saved_at':now(),'completed_original_ids':len(records),'source_values_hashes_and_quote_entities_valid':True,
        'scoped_checker_status':checked['status'],'scoped_checker_issue_counts':checked['issue_counts'],
        'full_file_checker_status':fullcheck['status'],'full_file_checker_issue_counts':fullcheck['issue_counts'],
        'full_file_count':660622,'classified_nonempty':100000,'empty_quarantines':13,'outside_sample_scope':560609,
        'verification_random_source_sample_exact':sample_ok,'model_inputs_source_only':source_only,
        'max_label_attempts_per_source_id':max(counts.values()),'ranking_identical_offline':ranking_same,
        'doubled_rates_double_spend':rates_ok,'doubled_rates_preserve_measured_time':time_ok,'changed_volume_preserves_measurements':volume_ok,
        'warm_new_calls':summary['warm_new_calls'],'global_committed_usd':str(global_amount),'under_shared_10_usd_cap':global_amount<=10}
    outcome['fully_reconciled_checker_pass']=checked['status']=='pass'
    outcome['passed']=all([not(set(checked['issue_counts'])-{'invalid_usage'}),sample_ok,source_only,ranking_same,rates_ok,time_ok,volume_ok,
        summary['warm_new_calls']==0,global_amount<=10,max(counts.values())<=3])
    write_json(evaluation/'acceptance.json',outcome)
    print(json.dumps(outcome,indent=2))
    raise SystemExit(0 if outcome['passed'] else 1)


if __name__=='__main__':main()
