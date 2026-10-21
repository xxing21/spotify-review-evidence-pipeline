"""Production orchestration checks with a simulated provider and temporary SQLite state."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from spotify_pipeline.common import config, digest, label_config
from spotify_pipeline.decisions import verification_prompt
from spotify_pipeline.production import canonical_rows, materialize_aliases, save_verification, verification_rows
from spotify_pipeline.scaling import WorkQueue, batches, process_phase
from spotify_pipeline.store import Store
from test_pipeline import source, FakeProvider
from test_scaling import NoWaitLimiter, decision_response


class ProductionTests(unittest.TestCase):
    def test_partial_refusal_is_explicit_and_does_not_relax_id_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Store(Path(tmp)/'state.sqlite3')
            rows=[source('one','Cannot play music'),source('two','Unclear wording')]
            cfg=config()|{'verification_fraction':.05}
            state.add_dataset('sample',rows,{})
            state.new_run('test','sample',cfg,{'scope':'synthetic only'})
            prediction={'review_id':'one','topic':'playback','intent':'complaint',
                'sentiment':-1,'severity':4,'entities':[],'evidence_quote':rows[0]['review_text'],'needs_review':False}
            partial={'review_id':'two','status':'partial_refusal','unavailable_fields':['topic']}
            state.put('test','verification_recovered_predictions',[prediction])
            state.put('test','verification_refusals',[partial])
            save_verification(state,'test',rows,cfg)
            saved=state.get('test','verification')
            self.assertEqual(saved['sample_ids'],['one','two'])
            self.assertEqual(saved['predictions'],[prediction])
            self.assertEqual(saved['refusals'],[partial])
            self.assertNotIn('topic',saved['refusals'][0])
            for invalid in [[partial|{'review_id':'foreign'}],[partial|{'review_id':'one'}],[],[partial,partial]]:
                state.put('test','verification_refusals',invalid)
                with self.assertRaisesRegex(ValueError,'incomplete, duplicated or contains foreign'):
                    save_verification(state,'test',rows,cfg)
            state.close()

    def test_deduplicate_checkpoint_resume_and_blind_five_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'state.sqlite3';state=Store(db)
            rows=[source(str(i),f'Cannot log in {i%40}. café\n音楽') for i in range(80)]
            cfg=config()|{'execution_mode':'production-100k-v1','workers':16,'batch_size':20,
                'schema_version':'spotify-label-v4-batch20','routing_schema':'review-id-enum-v1',
                'label_batch_identity':'batch-context-v1','verification_fraction':.05,
                'verification_endpoint':'decisions','verification_schema_version':'decisions-verifier-v3-batch10-five-levels',
                'verification_batch_size':10,'verification_sentiment_mapping':'index_0_4_to_minus1_plus1',
                'verification_predicate_threshold':.5,'pilot_run_cap_usd':10,'initial_phase':'enrich-probe'}
            cfg['prompt_hashes']['verify']=digest(verification_prompt())
            state.add_dataset('sample',rows,{})
            state.new_run('test','sample',cfg,{'scope':'synthetic only'})
            queue=WorkQueue(state);unique=canonical_rows(rows)
            queue.add('test','enrich','enrich-probe',batches(unique[:20],20),cfg)
            queue.add('test','enrich','enrich-16',batches(unique[20:],20),cfg)
            sent=[]
            def transport(payload):
                reviews=json.loads(payload['input'][1]['content'])['reviews']
                self.assertTrue(all(set(r)=={'review_id','review_text'} for r in reviews))
                if 'questions' in payload:
                    return decision_response(reviews)
                sent.extend(r['review_id'] for r in reviews)
                return FakeProvider()(payload)
            process_phase(db,'test',cfg,root,'enrich-probe',1,NoWaitLimiter(),time.monotonic()+15,transport)
            state.close();state=Store(db);queue=WorkQueue(state);queue.recover('test')
            process_phase(db,'test',cfg,root,'enrich-probe',1,NoWaitLimiter(),time.monotonic()+15,transport)
            process_phase(db,'test',cfg,root,'enrich-16',16,NoWaitLimiter(),time.monotonic()+15,transport)
            self.assertEqual(len(sent),40)
            self.assertEqual(materialize_aliases(state,'test',rows,cfg),40)
            self.assertEqual(materialize_aliases(state,'test',rows,cfg),0)
            records={r['review_id']:r for r in state.records('test')}
            self.assertEqual(len(records),80)
            self.assertEqual(sum(bool(r.get('cache_source_id')) for r in records.values()),40)
            for r in records.values():
                if r.get('cache_source_id'):
                    self.assertNotIn('cache_source_id',records[r['cache_source_id']])
                    self.assertEqual(r['label_config'],label_config(cfg))
            selected=verification_rows(rows,cfg)
            self.assertEqual(len(selected),4)
            self.assertEqual(selected,verification_rows(list(reversed(rows)),cfg))
            queue.add('test','verify','verify-8',batches(selected,10),cfg)
            process_phase(db,'test',cfg,root,'verify-8',8,NoWaitLimiter(),time.monotonic()+15,transport)
            save_verification(state,'test',selected,cfg)
            self.assertEqual(len(state.get('test','verification')['predictions']),4)
            self.assertEqual(len(sent),40)
            state.close()
