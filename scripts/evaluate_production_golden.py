"""Plan or explicitly execute a bounded final-configuration golden evaluation."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import config, label_config, now, require_key, sha, write_json
from spotify_pipeline.evaluation import check_human_labels, evaluate
from spotify_pipeline.pipeline import enrich, export, initialize
from spotify_pipeline.provider import ModelClient
from spotify_pipeline.store import Store, experiment_lock


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-paid',action='store_true')
    parser.add_argument('--budget-usd',type=Decimal,default=Decimal('.04'))
    args=parser.parse_args()
    if not 0 < args.budget_usd <= Decimal('.04'):
        raise ValueError('This evaluation is limited to US$0.04, inside the existing shared US$10 cap')
    original_labels=Path('evals/golden_labels.json')
    if check_human_labels(original_labels) is None:
        raise ValueError('All fifty original human labels must be complete')
    state=Store()
    try:
        parent=state.run('production-100k-v1')
        if not parent:raise ValueError('Completed production configuration is required')
        cfg=parent['config']
        if cfg['prompt_hashes']['enrich']!=config()['prompt_hashes']['enrich']:
            raise ValueError('The classification prompt changed; restore the production prompt before evaluation')
        identity=label_config(cfg)
        golden_id='golden-'+identity.split(':')[-1][:12]
        out=Path('evals/production_golden')
        plan={'saved_at':now(),'target_run_id':parent['run_id'],'golden_run_id':golden_id,
            'label_config':identity,'source_sha256':sha('golden_50_to_label.csv'),
            'original_human_labels_sha256':sha(original_labels),'sample_count':50,
            'batch_size':cfg['batch_size'],'schema_version':cfg['schema_version'],
            'evaluation_cap_usd':str(args.budget_usd),'shared_cap_usd':'10',
            'original_evaluation_preserved':True,'adjudicated_reference_used':False,
            'model_inputs':'original routing ID and text only; human answers never sent',
            'status':'prepared','paid_calls_dispatched':0}
        if not args.execute_paid:
            write_json(out/'plan.json',plan)
            print(json.dumps(plan,indent=2));return
        require_key()
        labels_before=sha(original_labels)
        old_report=sha('evals/golden_report.json')
        directory=Path('artifacts/evaluation')/golden_id
        with experiment_lock(Path('state/paid-command')):
            initialize(state,golden_id,'golden_50_to_label.csv',cfg,kind='golden_evaluation')
            before_calls=len(state.calls(golden_id))
            client=ModelClient(state,golden_id,cfg,10,directory,run_cap=args.budget_usd)
            try:
                enrich(state,golden_id,client,'production_golden')
            finally:
                export(state,golden_id,directory)
            predictions=state.records(golden_id)
            result=evaluate(state,parent['run_id'],original_labels,predictions,directory=out)
            assert sha(original_labels)==labels_before and sha('evals/golden_report.json')==old_report
            calls=state.calls(golden_id)
            known=sum((Decimal(c['calculated_api_usd']) for c in calls if c.get('calculated_api_usd') is not None),Decimal(0))
            unknown=[c for c in calls if c.get('calculated_api_usd') is None]
            proof=plan|{'saved_at':now(),'status':result['status'],'valid_predictions':result['valid_predictions'],
                'known_api_usd':str(known),'missing_usage_calls':len(unknown),
                'new_calls':len(calls)-before_calls,'paid_calls_dispatched':len(calls)-before_calls,'all_work_spent_plus_reserved_usd':str(state.committed_spend()),
                'human_labels_unchanged':True,'earlier_evaluation_unchanged':True,
                'agreement':result['agreement'],'severity_mae':result['severity_mae_on_valid'],
                'sentiment_mae':result['sentiment_mae_on_valid']}
            write_json(out/'acceptance.json',proof)
            write_json('cost/budget_ledger.json',{'cap_usd':10,'spent_plus_unresolved_reservations_usd':str(state.committed_spend()),
                'scope':'All experiments and production, including unresolved reservations'})
            print(json.dumps(proof,indent=2))
    finally:state.close()


if __name__=='__main__':main()
