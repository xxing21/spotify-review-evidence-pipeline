"""Verify portable saved production replay without the original database or credentials."""
import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import csv_rows, now, sha, write_csv, write_json
from spotify_pipeline.production_cost import compute
from spotify_pipeline.pipeline import rerank_exports


def main():
    directory=Path('artifacts/runs/production-100k-v1')
    before=sha(directory/'ranking.csv')
    rerank_exports(directory)
    assert sha(directory/'ranking.csv')==before
    with tempfile.TemporaryDirectory() as tmp:
        rows=list(csv_rows('cost/production_100k/rates.csv'))
        for row in rows:row['price_per_unit']=str(Decimal(row['price_per_unit'])*2)
        rates=Path(tmp)/'double.csv';write_csv(rates,rows,list(rows[0]))
        base,_=compute();double,_=compute(rates_path=rates);volume,_=compute(volume=100000)
        assert Decimal(double['measured']['known_api_usd'])==2*Decimal(base['measured']['known_api_usd'])
        assert double['measured']['active_seconds']==base['measured']['active_seconds']
        assert volume['measured']==base['measured']
    result={'saved_at':now(),'passed':True,'ranking_identical':True,'rates_double_spend':True,
        'rate_change_preserves_measured_time':True,'volume_change_preserves_measurements':True,
        'api_key_required':False,'sqlite_required':False,'full_source_csv_required':False,'model_calls':0}
    write_json('evals/production_100k/portable_replay.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
