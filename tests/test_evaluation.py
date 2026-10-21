"""A final evaluation must not overwrite the original blind comparison."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spotify_pipeline.evaluation import evaluate
from spotify_pipeline.common import LABEL_SCHEMA, config, ground_labels
from spotify_pipeline.provider import ModelClient, TransientError
from spotify_pipeline.store import Store
from test_pipeline import source, prediction


class EvaluationTests(unittest.TestCase):
    def test_final_verifier_attempt_respects_original_two_attempts_across_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=Store(root/'state.sqlite3');row=source('one')
            cfg=config()|{'verification_endpoint':'decisions','prior_verification_attempts':{'one':2},'max_task_attempts':1}
            state.new_run('repair','sample',cfg,{'scope':'synthetic control test'})
            dispatched=[]
            def failure(payload):
                dispatched.append(payload)
                raise TransientError('simulated temporary failure on the final permitted attempt')
            client=ModelClient(state,'repair',cfg,10,root,transport=failure,sleeper=lambda _:None,run_cap=.01)
            def attempt():
                return client.call('verify',{'reviews':[{'review_id':'one','review_text':row['review_text']}]},
                    LABEL_SCHEMA,lambda x:ground_labels(x,[row]),review_ids=['one'])
            with self.assertRaises(RuntimeError):attempt()
            self.assertEqual(len(dispatched),1)
            self.assertEqual(state.calls('repair')[0]['attempt'],3)
            with self.assertRaisesRegex(ValueError,'retry limit'):attempt()
            self.assertEqual(len(dispatched),1)
            state.close()

    def test_separate_final_report_preserves_original_reference_and_report(self):
        rows=[source(str(i)) for i in range(50)]
        cases=[prediction(r['review_id'],r['review_text'])|{'human_labeled':True,'ambiguous':False,'note':''} for r in rows]
        predictions=[prediction(r['review_id'],r['review_text'])|{'status':'completed'} for r in rows]
        # A deliberately wrong final prediction must remain a real disagreement.
        predictions[0]['severity']=1
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);labels=root/'human.json';labels.write_text(json.dumps({'source':'human','cases':cases}))
            original=root/'evals/golden_report.json';original.parent.mkdir();original.write_text('original report')
            before=labels.read_bytes();previous=Path.cwd()
            try:
                os.chdir(root)
                with patch('spotify_pipeline.evaluation.source_records',return_value=rows):
                    result=evaluate(None,'production',str(labels),predictions,directory=root/'evals/production_golden')
            finally:os.chdir(previous)
            self.assertEqual(result['valid_predictions'],50)
            self.assertEqual(result['agreement']['severity'],.98)
            self.assertEqual(original.read_text(),'original report')
            self.assertEqual(labels.read_bytes(),before)
            self.assertTrue((root/'evals/production_golden/golden_report.json').is_file())
            self.assertTrue((root/'evals/production_golden/error_analysis.md').is_file())
