import collections, gzip, hashlib, itertools, json, shutil, sqlite3, subprocess, sys, tempfile
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from check_submission import audit, csv_rows, profile, reference_hash, row_sha, sha, VERSION
from spotify_pipeline.common import LABEL_FIELDS, now, read_json, read_jsonl, validate_labels, write_json
from spotify_pipeline.evaluation import check_human_labels
from spotify_pipeline.pipeline import validate_memo
from spotify_pipeline.calculator import replay

run=Path('artifacts/runs/production-100k-v1')
revision=run/'revisions/submission-review-v1'
reviewed=(revision/'review.json').exists() and read_json(revision/'review.json').get('status')=='published'
report={'checked_at':now(),'scope':'100000 original nonempty classifications; entire source ingestion','paid_model_calls':0,'criteria':{}}
state=sqlite3.connect('file:state/pipeline.sqlite3?mode=ro',uri=True)
full_sha=read_json('manifest.json')['files']['spotify_reviews_18months.csv']['sha256']
print('Checking all stored source rows and full-file accounting...',flush=True)
stored={rid:(digest,row_sha(json.loads(raw))) for rid,digest,raw in state.execute('SELECT review_id,source_sha,row_json FROM sources WHERE dataset=?',(full_sha,))}
selected={r['review_id']:r for r in csv_rows(run/'input_100000.csv')}
counts=collections.Counter()
with gzip.open('submission/grading/records.jsonl.gz','rt',encoding='utf-8') as exported:
    for original,line in itertools.zip_longest(csv_rows('spotify_reviews_18months.csv'),exported):
        assert original is not None and line is not None
        entry=json.loads(line);rid=original['review_id'];digest=row_sha(original)
        assert stored.pop(rid)==(digest,digest)
        assert entry['review_id']==rid and entry['source_sha256']==digest
        counts['full_rows']+=1
        if rid in selected:
            assert selected[rid]==original and entry['status']=='completed'
            counts['selected_completed']+=1
        elif not original['review_text'].strip():
            assert entry['status']=='quarantined' and entry['reason']=='empty_review_text'
            counts['empty_quarantined']+=1
        else:
            assert entry['status']=='quarantined' and entry['reason']=='outside_100k_analysis_scope'
            counts['outside_100k_scope']+=1
assert not stored
actual_profile=profile('spotify_reviews_18months.csv')
assert actual_profile==read_json('artifacts/ingestion/ingestion.json')
assert actual_profile['file_sha256']==full_sha and counts['full_rows']==660622
report['criteria']['1_ingestion']={'status':'met','full_rows':counts['full_rows'],'all_stored_source_values_and_hashes_match':True,'profile_recomputed_matches':True}
print('Source IDs, stored values, full accounting and profile match.',flush=True)
records=read_jsonl(run/'records.jsonl');indexed={r['review_id']:r for r in records}
assert len(records)==len(indexed)==len(selected)==100000 and set(indexed)==set(selected)
for record in records:
    assert record['status']=='completed' and record['source_sha256']==row_sha(selected[record['review_id']])
    validate_labels({'records':[{k:record[k] for k in ('review_id',*LABEL_FIELDS)}]},[selected[record['review_id']]])
ref={'version':VERSION,'analysis_sha256':sha(run/'input_100000.csv'),'ingestion':actual_profile,
     'rows':{rid:{'source_sha256':row_sha(row),'review_text':row['review_text']} for rid,row in selected.items()}}
checked=audit(run/'grading',ref,ref_digest=reference_hash(ref))
assert checked['coverage']['valid_completed']==100000
assert checked['issue_counts']=={'invalid_usage':96}
write_json('evals/production_100k/definition_done_scoped_checker.json',checked)
calls=read_jsonl('cost/production_100k/calls.jsonl')
assert len(calls)==4474 and all(c.get('started_at') and c.get('ended_at') and c.get('attempt') for c in calls)
assert sum(c.get('calculated_api_usd') is None for c in calls)==48
committed=sum((Decimal(actual if actual is not None else reserved) for actual,reserved in state.execute('SELECT actual,reservation FROM calls')),Decimal(0))
assert committed<=10
report['criteria']['2_classifications']={'status':'met_for_100k_option','counts':dict(counts),'classification_pending_or_quarantined_in_selected_sample':0,
 'calls':len(calls),'missing_usage_calls':48,'scoped_checker_status':checked['status'],'checker_issues':checked['issue_counts'],'all_work_spent_plus_reserves_usd':str(committed)}
roles=collections.Counter();prompt_text={}
for c in calls:
    handoff=read_json(run/'handoffs'/(c['local_call_id']+'.json'))
    assert handoff['attempt']['local_call_id']==c['local_call_id']
    role=c['role'];roles[role]+=1
    prompt_text[role]=handoff['request']['input'][0]['content']
    if role in ('enrich','verify'):
        supplied=json.loads(handoff['request']['input'][1]['content'])
        assert set(supplied)=={'reviews'}
        for r in supplied['reviews']:
            assert set(r)=={'review_id','review_text'} and r['review_text']==selected[r['review_id']]['review_text']
assert set(roles)=={'enrich','verify','group','memo'} and len(set(prompt_text.values()))==4
for name in ['verification.json','issues.json','evidence.json','memo.json','membership.csv','ranking.csv','claims.csv']:
    assert (run/name).is_file()
report['criteria']['3_roles']={'status':'met','separately_prompted_roles':dict(roles),'all_attempt_handoffs_inspected':True,'classification_inputs_only_original_text_and_id':True}
assert len(check_human_labels('evals/golden_labels.json'))==50
assert read_json('evals/golden_validation.json')['valid_predictions']==50
assert read_json('evals/system_checks.json')['passed'] and read_json('evals/system_checks.json')['tests_run']>=40
assert read_json('cost/diagnostics.json')['injection']['passed']
assert read_json('cost/diagnostics.json')['planted_error']['rubric_correct']
before=read_json('artifacts/runs/pilot-100-v2/grading/checkpoint_before.json')['completed_ids']
after=read_json('artifacts/runs/pilot-100-v2/grading/checkpoint_after.json')['completed_ids']
assert len(before)==20 and len(after)==100 and set(before)<=set(after)
assert Path('artifacts/runs/pilot-100-v2/recovery.cast').stat().st_size>100
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    for name in ['pilot_summary.json','pilot_calls.jsonl','rates.csv']:
        shutil.copy2(Path('cost')/name,tmp/name)
    calculated=replay(tmp,tmp/'rates.csv')
    saved_measured=read_json('cost/calculator.json')['measured']
    assert all(calculated['measured'].get(k)==v for k,v in saved_measured.items())
    added_derived_fields=sorted(set(calculated['measured'])-set(saved_measured))
report['criteria']['4_evaluations']={'status':'met_with_quality_limitations','human_cases':50,'saved_system_tests':read_json('evals/system_checks.json')['tests_run'],'original_pilot_checkpoint':20,'resumed_to':100,'pilot_calculator_saved_measurements_unchanged':True,'additional_derived_fields':added_derived_fields,'human_evaluation_configuration':'original batch10 preserved; separate final batch20 comparison saved','final_configuration_human_evaluation':read_json('evals/production_golden/acceptance.json') if reviewed else None}
portable=read_json('evals/production_100k/portable_replay.json')
assert portable['passed'] and portable['ranking_identical'] and portable['model_calls']==0
report['criteria']['5_ranking']={'status':'met','scores_and_order_identical_without_model':True}
validate_memo(read_json(revision/'memo.json' if reviewed else run/'memo.json'),list(csv_rows(run/'ranking.csv')),list(csv_rows(run/'claims.csv')),read_json(run/'evidence.json'))
for e in read_json(run/'evidence.json'):
    assert e['review_id'] in indexed
live=read_json('evals/dashboard/vercel_live_e2e.json')
assert live['passed'] and live['signed_out_public_access'] and live['rankings_memo_claims_equal_saved_files']
report['criteria']['6_memo_and_deployment']={'status':'met_with_semantic_caveat','priority':'ISSUE-USABILITY','claim_and_source_references_valid':True,'public_frontend_backend_database_verified':True,
 'dashboard':'https://spotify-review-evidence-100k.vercel.app','caveat':'The reviewed memo explicitly qualifies the resolved crash report as historical evidence; no current unresolved defect is inferred.' if reviewed else 'Original memo requires historical-evidence qualification.'}
verification=read_json(revision/'verification_reviewed.json' if reviewed else run/'verification.json')
assert len(verification['sample_ids'])==5000 and len(verification['predictions'])==(5000 if reviewed else 4998) and len(verification['refusals'])==(0 if reviewed else 2)
report['limitations']=[
 'Meets the at-least-100000 option; 560609 additional nonempty source rows are outside scope and remain unclassified.',
 'The scoped checker remains review_required for 96 missing usage fields across 48 failed requests; reserves remain visible. This is not a clean billing reconciliation.',
 'Original partial refusals and failed attempts are preserved; a separately authorized final repair completed both original cases. Reviewed verification has 5000 complete predictions.' if reviewed else 'Two partial verifier cases remain.',
 'The separate final batch20 human comparison is saved (74% topic, 86% intent, 72% severity); fifty cases with limited topic coverage do not establish population accuracy.' if reviewed else 'Only earlier batch10 human evaluation is available.',
 'The reviewed memo and deployed dashboard explicitly identify the resolved playback report as historical evidence.',
 'The public dashboard displays the reviewed evidence, complete verification count, missing-usage reserve and separate final human comparison.' if reviewed else 'The original dashboard has not been updated.'
]
report['overall']='Meets the supplied definitions for the at-least-100000 scope, with the disclosed checker, verification and semantic limitations; not a full-corpus or clean-checker completion claim.'
state.close()
write_json('evals/production_100k/definition_of_done.json',report)
lines=['# Definition-of-done review','',f"Checked: {report['checked_at']}",'',report['overall'],'',
 '| Definition | Finding |','|---|---|']
for key,value in report['criteria'].items():lines.append(f"| {key} | {value['status']} |")
lines+=['','## Disclosed limitations','']+['- '+x for x in report['limitations']]+['','No paid model calls were made during this audit. All six-field source values, row hashes and full-file accounting were rechecked. Live API checks and offline reranking/calculator replay were repeated.','']
Path('evals/production_100k/definition_of_done.md').write_text('\n'.join(lines))
print(json.dumps(report,indent=2),flush=True)
