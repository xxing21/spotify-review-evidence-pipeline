"""Recover complete rows from refused verifier batches while retaining unresolved answers. Offline only."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import ground_labels, now, read_json, write_json
from spotify_pipeline.decisions import parse_decision
from spotify_pipeline.store import Store


def main():
    run='production-100k-v1';directory=Path('artifacts/runs')/run;state=Store()
    try:
        prior=state.get(run,'verification_refusal_recovery',{})
        failed=state.db.execute("SELECT task_key FROM scaling_queue WHERE run_id=? AND role='verify' AND status='failed'",(run,)).fetchall()
        if not failed:
            print(json.dumps({'status':'no_unhandled_failed_tasks','new_model_calls':0}));return
        recovered=state.get(run,'verification_recovered_predictions',[])
        refusals=state.get(run,'verification_refusals',[])
        traces=list(prior.get('task_recoveries',[]))
        if prior.get('source_task_key') and not traces:
            traces=[{'source_task_key':prior['source_task_key'],'source_call_ids':prior['partial_refusals'][0]['source_call_ids']}]
        for key, in failed:
            events=[json.loads(row[0]) for row in state.db.execute("SELECT event FROM calls WHERE run_id=? AND json_extract(event,'$.queue_task_key')=? ORDER BY rowid",(run,key))]
            if len(events)!=2 or any(e.get('error_kind')!='invalid_output' for e in events):
                raise ValueError('Recovery requires the original allowed pair of invalid-output attempts')
            refusal_sets=[]
            for event in events:
                h=read_json(directory/'handoffs'/(event['local_call_id']+'.json'))
                questions=h['request']['questions'];answers=h['response']['answers']
                if len(answers)!=len(questions) or len({a['name'] for a in answers})!=len(questions):raise ValueError('Missing or duplicate answers cannot be recovered')
                refused=[]
                for q,a in zip(questions,answers):
                    if a['name']!=q['name']:raise ValueError('Foreign/reordered answers cannot be recovered')
                    if a['type']=='refusal':refused.append(a['name'])
                    elif a['type']!=q['type']:raise ValueError('Unexpected answer type')
                refusal_sets.append(refused)
            if not refusal_sets[0] or refusal_sets[0]!=refusal_sets[1]:raise ValueError('Both attempts must refuse the same declared questions')
            reviews=json.loads(h['request']['input'][1]['content'])['reviews']
            rejected_ids={name.rsplit(':',1)[0] for name in refusal_sets[0]}
            complete=[r for r in reviews if r['review_id'] not in rejected_ids]
            answers=[a for a in h['response']['answers'] if a['name'].rsplit(':',1)[0] not in rejected_ids]
            batch=ground_labels(parse_decision({'answers':answers},complete),complete)['records'] if complete else []
            recovered.extend(batch)
            for rejected_id in rejected_ids:
                refusals.append({'review_id':rejected_id,'status':'partial_refusal',
                    'unavailable_fields':[name.rsplit(':',1)[1] for name in refusal_sets[0] if name.rsplit(':',1)[0]==rejected_id],
                    'original_text':next(r['review_text'] for r in reviews if r['review_id']==rejected_id),
                    'available_raw_answers':[a for a in h['response']['answers'] if a['name'].rsplit(':',1)[0]==rejected_id and a['type']!='refusal'],
                    'source_call_ids':[e['local_call_id'] for e in events],
                    'handling':'No replacement label inferred; unavailable answers retained; partial predictions excluded from complete-prediction agreement/MAE denominators'})
            traces.append({'source_task_key':key,'source_call_ids':[e['local_call_id'] for e in events],
                'recovered_complete_rows':len(batch),'partial_rows':len(rejected_ids)})
        if len({r['review_id'] for r in recovered+refusals})!=len(recovered)+len(refusals):raise ValueError('Recovery would create duplicate IDs')
        report={'saved_at':now(),'run_id':run,'recovered_complete_predictions':len(recovered),'partial_refusals':refusals,
            'task_recoveries':traces,'raw_failed_attempts_preserved':True,'new_model_calls':0,'enrichment_relabeling':False}
        state.put(run,'verification_recovered_predictions',recovered)
        state.put(run,'verification_refusals',refusals)
        state.put(run,'verification_refusal_recovery',report)
        with state.db:
            for key, in failed:
                state.db.execute("UPDATE scaling_queue SET status='resolved_partial',error=? WHERE run_id=? AND task_key=?",
                    ('Complete rows recovered from raw response; refusals retained; no additional model attempt',run,key))
        write_json(directory/'verification_refusal_recovery.json',report)
        print(json.dumps({'recovered_complete_predictions':len(recovered),'partial_refusals':len(refusals),'new_model_calls':0}))
    finally:state.close()


if __name__=='__main__':main()
