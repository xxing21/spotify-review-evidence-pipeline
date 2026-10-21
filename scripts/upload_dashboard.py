"""Idempotently upload actual SQLite results to the hosted dashboard. Never calls a model."""
import argparse
import concurrent.futures
import getpass
import hashlib
import json
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import LABEL_FIELDS, csv_rows, now, read_json, sha, write_json
from spotify_pipeline.pipeline import validate_memo


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--partial',action='store_true',help='Publish actual saved progress while the run is incomplete')
    parser.add_argument('--reviewed',action='store_true',help='Explicitly publish the validated reviewed memo and any accepted supplemental verification')
    args=parser.parse_args()
    origin=args.url.rstrip('/')
    if origin not in {'https://spotify-review-evidence-100k.vercel.app','https://spotify-review-evidence-100k.black-jelly-1742.chatgpt.site'}:
        raise ValueError('Upload is bound to this assignment dashboard origin')
    credential=json.loads(getpass.getpass('Dashboard credentials JSON (hidden): '))
    headers={'Authorization':'Bearer '+credential['import_token'],'Content-Type':'application/json'}
    if credential.get('service_token'):
        headers['OAI-Sites-Authorization']='Bearer '+credential['service_token']
    run='production-100k-v1'
    connection=sqlite3.connect('file:state/pipeline.sqlite3?mode=ro',uri=True)
    connection.execute('BEGIN')
    summary_row=connection.execute("SELECT value FROM artifacts WHERE run_id=? AND name='production_summary'",(run,)).fetchone()
    summary=json.loads(summary_row[0]) if summary_row else {}
    if not args.partial and summary.get('status')!='completed':
        raise ValueError('A complete saved run is required; use --partial explicitly for progress')
    rows=[]
    for prediction,source in connection.execute("SELECT r.result,s.row_json FROM records r JOIN runs u ON u.id=r.run_id JOIN sources s ON s.dataset=u.dataset AND s.review_id=r.review_id WHERE r.run_id=? ORDER BY r.review_id",(run,)):
        record=json.loads(prediction)
        if record['status']=='completed':
            original=json.loads(source)
            rows.append(record|{'review_text':original['review_text'],'source':original})
    calls=[json.loads(row[0]) for row in connection.execute('SELECT event FROM calls WHERE run_id=? ORDER BY rowid',(run,))]
    saved={name:json.loads(value) for name,value in connection.execute('SELECT name,value FROM artifacts WHERE run_id=?',(run,))}
    global_committed=sum((Decimal(actual if actual is not None else reserved) for actual,reserved in connection.execute('SELECT actual,reservation FROM calls')),Decimal(0))
    connection.close()
    revised_verification=False
    if args.reviewed:
        root=Path('artifacts/runs')/run;revised=root/'revisions/submission-review-v1'
        review=read_json(revised/'review.json')
        for key,name in [('original_memo_sha256','memo.json'),('records_sha256','records.jsonl'),('ranking_sha256','ranking.csv'),('claims_sha256','claims.csv')]:
            if sha(root/name)!=review[key]:raise ValueError('Reviewed memo provenance changed; prepare and inspect it again')
        memo=read_json(revised/'memo.json')
        if sha(revised/'memo.json')!=review['reviewed_memo_sha256']:raise ValueError('Reviewed memo differs from its approved draft')
        validate_memo(memo,list(csv_rows(root/'ranking.csv')),list(csv_rows(root/'claims.csv')),saved['evidence'])
        saved['memo']=memo
        if (revised/'verification_reviewed.json').exists():
            repair=read_json(revised/'verification_repair_result.json')
            candidate=read_json(revised/'verification_reviewed.json')
            if repair['status']!='completed' or candidate['sample_ids']!=saved['verification']['sample_ids']:
                raise ValueError('Supplemental verification is incomplete or changes the declared sample')
            combined=candidate['predictions']+candidate.get('refusals',[])
            if len(combined)!=5000 or {r['review_id'] for r in combined}!=set(candidate['sample_ids']):raise ValueError('Invalid reviewed verification coverage')
            saved['verification']=candidate;revised_verification=True
    known=sum((Decimal(c['calculated_api_usd']) for c in calls if c.get('calculated_api_usd') is not None),Decimal(0))
    progress=read_json('artifacts/runs/production-100k-v1/progress.json')
    metadata={'known_api_usd':str(known),'cost_as_of':now(),'full_source_rows':660622,'full_source_empty_texts':13,
        'expected_distinct_texts':78288,'verification_fraction':.05,'snapshot_records':len(rows),
        'snapshot_note':'Actual saved SQLite results, not a new model execution',
        'global_committed_usd':str(global_committed),'reviewed_memo':args.reviewed,'reviewed_verification':revised_verification}
    unknown=[c for c in calls if c.get('calculated_api_usd') is None]
    metadata.update(unknown_usage_calls=len(unknown),unresolved_reserved_usd=str(sum((Decimal(c['reservation_usd']) for c in unknown),Decimal(0))))
    def post(payload):
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
        for attempt in range(3):
            try:
                opener=urllib.request.build_opener(NoRedirect())
                with opener.open(urllib.request.Request(origin+'/api/import',data=encoded,headers=headers),timeout=90) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code not in (429,500,502,503,504) or attempt==2:
                    raise RuntimeError(f'Dashboard import returned HTTP {error.code}; credential/body omitted') from None
            except (urllib.error.URLError,TimeoutError):
                if attempt==2:
                    raise RuntimeError('Dashboard import network failure; idempotent progress preserved') from None
            time.sleep(2**attempt)
    print(f'Uploading {len(rows):,} actual saved reviews; zero model calls.',flush=True)
    post({'type':'run','run_id':run,'target':100000,'metadata':metadata})
    checkpoint_path=Path('artifacts/runs')/run/('dashboard_upload_checkpoint_'+hashlib.sha256(origin.encode()).hexdigest()[:10]+'.json')
    checkpoint=read_json(checkpoint_path) if checkpoint_path.exists() else {'origin':origin,'completed_batches':[]}
    if checkpoint['origin']!=origin:
        raise ValueError('Dashboard upload origin changed')
    completed=set(checkpoint['completed_batches']);lock=threading.Lock();uploaded=0
    def upload_chunk(task):
        nonlocal uploaded
        key,payload=task
        if key not in completed:
            post(payload)
            with lock:
                completed.add(key)
                write_json(checkpoint_path,{'origin':origin,'completed_batches':sorted(completed),'updated_at':now()})
        with lock:
            uploaded+=len(payload['rows'])
            if uploaded%2000==0:
                print(f'Saved {uploaded:,} rows to hosted database.',flush=True)
    tasks=[]
    outcomes=saved.get('verification',{}).get('predictions',[])+saved.get('verification',{}).get('refusals',[])
    for kind,items in [('reviews',rows),('attempts',calls),('checks',outcomes)]:
        for offset in range(0,len(items),100):
            payload={'type':kind,'rows':items[offset:offset+100]}
            key=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            tasks.append((key,payload))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(upload_chunk,tasks):
            pass
    artifacts=[{'name':name,'value':saved[name]} for name in ['memo','issues','evidence','claims'] if name in saved]
    artifacts.append({'name':'summary','value':summary})
    verification=saved.get('verification')
    if verification:
        indexed={r['review_id']:r for r in rows};predictions=verification['predictions'];n=len(predictions)
        quality={'sample_count':len(verification['sample_ids']),'complete_prediction_count':n,'refusal_count':len(verification.get('refusals',[])),
            'metric_denominator':n,'method':'Independent same-model-family consistency; complete-prediction denominators exclude explicit partial refusals; not human accuracy',
            'core_label_disagreements':verification['label_disagreements'],
            'agreement':{field:sum(p[field]==indexed[p['review_id']][field] for p in predictions)/n for field in LABEL_FIELDS},
            'severity_mae':sum(abs(p['severity']-indexed[p['review_id']]['severity']) for p in predictions)/n,
            'sentiment_mae':sum(abs(p['sentiment']-indexed[p['review_id']]['sentiment']) for p in predictions)/n}
        golden_path=Path('evals/production_golden/acceptance.json')
        if args.reviewed and golden_path.exists():
            golden=read_json(golden_path)
            if golden.get('status')=='completed':
                quality['production_golden']={k:golden[k] for k in ('status','target_run_id','sample_count','valid_predictions',
                    'batch_size','label_config','original_human_labels_sha256','agreement','severity_mae','sentiment_mae')}
        artifacts.append({'name':'quality','value':quality})
    post({'type':'artifacts','rows':artifacts})
    final=None
    if not args.partial:
        final=post({'type':'finalize'})
    report={'saved_at':now(),'origin':origin,'source_run':run,'uploaded_reviews':len(rows),'uploaded_checks':len(outcomes),
        'complete_verifier_predictions':len(saved.get('verification',{}).get('predictions',[])),'verifier_refusal_count':len(saved.get('verification',{}).get('refusals',[])),
        'uploaded_attempts':len(calls),'partial':args.partial,'finalization':final,'model_calls':0}
    report.update(reviewed_memo=args.reviewed,reviewed_verification=revised_verification)
    write_json('evals/dashboard/upload_report.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
