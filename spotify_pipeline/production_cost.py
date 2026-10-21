"""Offline billing and stage-specific projections from the actual 100k run."""
from decimal import Decimal, ROUND_CEILING
from datetime import datetime
from pathlib import Path

from .calculator import calculate
from .common import atomic_text, read_json, read_jsonl, write_csv, write_json
from .provider import rates
from .scaling_cost import sustained_limits


def compute(directory="cost/production_100k", rates_path=None, volume=660622):
    root=Path(directory)
    summary=read_json(root/"run_summary.json")
    calls=read_jsonl(root/"calls.jsonl")
    result,units=calculate(calls,summary|{"status":"offline_billing_only"},rates(rates_path or root/"rates.csv"),volume=volume,budget=10)
    result["measured"]["status"]=summary["status"]
    result["measured"]["verification_complete_prediction_count"]=summary.get("verification_complete_prediction_count",0)
    result["measured"]["verification_refusal_count"]=summary.get("verification_refusal_count",0)
    starts=[datetime.fromisoformat(c['started_at']) for c in calls if c.get('started_at')]
    ends=[datetime.fromisoformat(c['ended_at']) for c in calls if c.get('ended_at')]
    result["measured"]["first_dispatch_to_last_response_seconds"]=(max(ends)-min(starts)).total_seconds() if starts and ends else None
    result["projections"]=[]
    if summary["status"]=="completed":
        if type(volume) is not int or volume<1:
            raise ValueError("Projected volume must be positive")
        nonempty=660609 if volume==660622 else volume
        empty=13 if volume==660622 else 0
        distinct=484189 if volume==660622 else summary["unique_texts"] if volume==100000 else round(nonempty*484189/660609)
        limits=sustained_limits(calls)
        timing={p["phase"]:p["seconds"] for p in summary["phase_measurements"]}
        measured_enrichment=sum(p["seconds"] for p in summary["phase_measurements"] if p["phase"].startswith('enrich'))
        measured_verification=sum(p["seconds"] for p in summary["phase_measurements"] if p["phase"].startswith('verify'))
        overhead=max(0,summary["active_seconds"]-measured_enrichment-measured_verification)
        stages=result["stages"]
        for reuse,count in ((True,distinct),(False,nonempty)):
            for conservative in (False,True):
                cost=sum((Decimal(stages[r]["known_api_usd"]) for r in ('group','memo')),Decimal(0))
                seconds=overhead
                work_counts={}
                for role,work,denom,observed_time in [('enrich',count,summary['unique_texts'],measured_enrichment),
                    ('verify',int((Decimal(nonempty)*Decimal('.05')).to_integral_value(rounding=ROUND_CEILING)),summary['verification_count'],measured_verification)]:
                    s=stages[role]
                    retry=s['failed_attempts']/max(1,s['attempts']-s['failed_attempts'])
                    factor=(1+max(.1,retry))/(1+retry) if conservative else 1
                    cost+=Decimal(s['known_api_usd'])/denom*work*Decimal(str(factor))
                    measured=observed_time/denom*work
                    tokens=(s['input_tokens']+s['output_tokens'])/denom*work/limits['tpm']*60
                    requests=s['attempts']/denom*work/limits['rpm']*60
                    seconds+=max(measured,tokens,requests)*factor*(1.5 if conservative else 1)
                    work_counts[role]=work
                result['projections'].append({'scenario':('conservative' if conservative else 'base')+('_exact_reuse' if reuse else '_no_reuse'),
                    'estimated_api_usd':str(cost),'estimated_seconds':seconds,'input_rows':volume,'empty_quarantines':empty,
                    'nonempty_classifications':nonempty,'stage_work':work_counts,'verification_fraction':.05,'fallback_fraction':0,
                    'workers':16,'fixed_overhead_seconds':overhead,'sustained_rate_limits':limits,'estimate_not_execution':True})
    result['controls']={'shared_budget_usd':10,'max_workers':16,'verification_fraction':.05,'max_output_tokens':4096,'fallback_fraction':0}
    result['projection_notes']=['Estimates use actual 100k stage throughput and mutually exclusive saved usage categories.',
        'Grouping and memo overhead is added once. Conservative variable work includes at least 10% retries and 50% slower throughput.',
        'Time is bounded by measured throughput and the sustained shared request/token ceilings; burst speed is not extrapolated indefinitely.',
        'Full-corpus exact-text counts are known from ingestion. Other unprofiled volumes use the corpus distinct/nonempty ratio.',
        'Unknown usage stays visible with reservations; it is not zero. Recorded usage times editable prices is not an invoice.',
        'Pipeline active time excludes source preparation, manual checkpoint waiting, final export/upload and hosting work; these are not fabricated as measured zero.',
        'Local hardware/electricity and hosting costs are separate and unmeasured.']
    return result,units


def replay(directory="cost/production_100k",rates_path=None,volume=660622):
    root=Path(directory)
    result,units=compute(root,rates_path,volume)
    write_json(root/'calculator.json',result)
    write_csv(root/'usage.csv',units,['local_call_id','role','item','billed_units','price_per_unit','calculated_usd','currency'])
    m=result['measured']
    lines=['# Actual 100k run and offline calculator','',f"Status: **{m['status']}**",'',
        f"Completed original IDs: {m['completed']:,} / 100,000; independent checks: {m['verification_count']:,} (5%).",
        f"Complete independent predictions: {m['verification_complete_prediction_count']:,}; explicit partial refusals: {m['verification_refusal_count']}. Agreement/MAE denominators exclude partial refusals.",
        f"Distinct text classifications: {m['unique_texts']:,}; exact-text aliases: {m['exact_text_reuses']:,}.",
        f"Active pipeline time: {m['active_seconds']/60:.2f} minutes. Warm replay: {m.get('warm_seconds')} seconds; {m.get('warm_new_calls')} new calls.",
        f"First paid dispatch to final response: {m['first_dispatch_to_last_response_seconds']/60:.2f} minutes, including interruption/manual recovery gaps; final exports and website deployment are separate.",
        f"Known API charge estimate: US${m['known_api_usd']}. Unresolved reservations for this run: US${m['unresolved_reservation_usd']}.",
        f"Global ledger including prior work/reservations at completion: US${m['global_committed_usd']} / US$10.",'',
        '| Role | Attempts | Failures | Input tokens | Output tokens | Estimated API USD |','|---|---:|---:|---:|---:|---:|']
    for role,s in result['stages'].items():
        lines.append(f"| {role} | {s['attempts']} | {s['failed_attempts']} | {s['input_tokens']} | {s['output_tokens']} | {s['known_api_usd']} |")
    lines+=['',f'## Estimated {volume:,}-row execution — not a new run','', '| Scenario | Estimated API USD | Estimated hours |','|---|---:|---:|']
    for p in result['projections']:
        lines.append(f"| {p['scenario']} | {Decimal(p['estimated_api_usd']):.3f} | {p['estimated_seconds']/3600:.2f} |")
    lines+=['']+['- '+n for n in result['projection_notes']]+['','```sh','python3 -m spotify_pipeline production-replay','```','']
    atomic_text(root/'report.md','\n'.join(lines))
    return result
