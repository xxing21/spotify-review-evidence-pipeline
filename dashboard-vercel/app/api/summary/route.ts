import { artifact,currentRun,database,json } from '../../../lib/data';
export async function GET(){try{
 const run=await currentRun();if(!run)return json({status:'awaiting_saved_data',completed:0,target:100000});
 const [counts,ranked,verification,memo,issues,evidence,claims,quality]=await Promise.all([
  database().prepare("SELECT COUNT(*) AS completed,SUM(CASE WHEN cache_origin IS NOT NULL THEN 1 ELSE 0 END) AS cache_reuses,SUM(CASE WHEN intent IN ('complaint','cancellation') THEN 1 ELSE 0 END) AS complaints,SUM(needs_review) AS needs_review FROM reviews WHERE run_id=?").bind(run.id).first<any>(),
  database().prepare("SELECT topic,COUNT(*) AS complaint_count,SUM(severity) AS severity_sum FROM reviews WHERE run_id=? AND intent IN ('complaint','cancellation') GROUP BY topic ORDER BY severity_sum DESC,topic ASC").bind(run.id).all<any>(),
  database().prepare('SELECT COUNT(*) AS checked FROM checks WHERE run_id=?').bind(run.id).first<any>(),
  artifact(run.id,'memo'),artifact(run.id,'issues'),artifact(run.id,'evidence'),artifact(run.id,'claims'),artifact(run.id,'quality')]);
 const names=new Map((issues||[]).map((r:any)=>[r.issue_id,r]));
 const ranking=ranked.results.map((r:any,i:number)=>({...r,rank:i+1,issue_id:'ISSUE-'+r.topic.toUpperCase(),priority_score:r.severity_sum,mean_severity:(Math.floor(r.severity_sum*1000000/r.complaint_count+.5)/1000000).toFixed(6),name:(names.get('ISSUE-'+r.topic.toUpperCase()) as any)?.name||r.topic,description:(names.get('ISSUE-'+r.topic.toUpperCase()) as any)?.description||''}));
 return json({run_id:run.id,status:run.status,target:run.target,updated_at:run.updated_at,...JSON.parse(run.metadata),...counts,verified:verification.checked,ranking,memo,issues,evidence,claims,quality});
 }catch{return json({error:'Saved analysis is temporarily unavailable'},503)}}
