import { database,intents,json,topics } from '../../../lib/data';
export async function POST(request:Request){
 const token=process.env.IMPORT_TOKEN;
 if(!token||request.headers.get('authorization')!=='Bearer '+token)return json({error:'Unauthorized'},401);
 if(Number(request.headers.get('content-length')||0)>1500000)return json({error:'Batch too large'},413);
 try{
 const body=await request.json() as any;const run='production-100k-v1';const db=database();
 if(body.type==='run'){
  if(body.run_id!==run||body.target!==100000)return json({error:'Unexpected run'},400);
  await db.prepare("INSERT INTO runs(id,status,target,updated_at,metadata) VALUES (?,'running',?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,metadata=excluded.metadata")
  .bind(run,body.target,new Date().toISOString(),JSON.stringify(body.metadata||{})).run();return json({saved:true});
 }
 if(body.type==='artifacts'){
  if(!Array.isArray(body.rows)||body.rows.length>20)throw new Error('Invalid artifact batch');
  const allowed=['memo','issues','evidence','claims','quality','summary'];
  if(body.rows.some((r:any)=>!allowed.includes(r.name)))throw new Error('Unknown artifact');
  await db.batch(body.rows.map((r:any)=>db.prepare('INSERT INTO artifacts VALUES (?,?,?) ON CONFLICT(run_id,name) DO UPDATE SET value=excluded.value').bind(run,r.name,JSON.stringify(r.value))));return json({saved:body.rows.length});
 }
 if(body.type==='reviews'){
  if(!Array.isArray(body.rows)||body.rows.length>100||!body.rows.length)throw new Error('Invalid review batch');
  const statements=body.rows.map((r:any)=>{
   if(typeof r.review_id!=='string'||!topics.includes(r.topic)||!intents.includes(r.intent)||!Number.isInteger(r.severity)||r.severity<1||r.severity>5||!Number.isFinite(r.sentiment)||r.sentiment < -1||r.sentiment>1||typeof r.review_text!=='string'||!r.evidence_quote||!r.review_text.includes(r.evidence_quote)||typeof r.needs_review!=='boolean'||!Array.isArray(r.entities))throw new Error('Invalid review');
   return db.prepare('INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,id) DO UPDATE SET topic=excluded.topic,intent=excluded.intent,severity=excluded.severity,sentiment=excluded.sentiment,body=excluded.body,evidence=excluded.evidence,needs_review=excluded.needs_review,entities=excluded.entities,source_hash=excluded.source_hash,cache_origin=excluded.cache_origin,source=excluded.source')
    .bind(run,r.review_id,r.topic,r.intent,r.severity,r.sentiment,r.review_text,r.evidence_quote,Number(r.needs_review),JSON.stringify(r.entities),r.source_sha256,r.cache_source_id||null,JSON.stringify(r.source));
  });await db.batch(statements);return json({saved:statements.length});
 }
 if(['checks','attempts'].includes(body.type)){
  if(!Array.isArray(body.rows)||body.rows.length>100)throw new Error('Invalid batch');
  const table=body.type;await db.batch(body.rows.map((r:any)=>db.prepare('INSERT INTO '+table+' VALUES (?,?,?) ON CONFLICT(run_id,id) DO UPDATE SET value=excluded.value').bind(run,table==='checks'?r.review_id:r.local_call_id,JSON.stringify(r))));return json({saved:body.rows.length});
 }
 if(body.type==='finalize'){
  const count=await db.prepare('SELECT COUNT(*) AS n FROM reviews WHERE run_id=?').bind(run).first<any>();
  const checks=await db.prepare('SELECT COUNT(*) AS n FROM checks WHERE run_id=?').bind(run).first<any>();
  const artifacts=await db.prepare("SELECT COUNT(*) AS n FROM artifacts WHERE run_id=? AND name IN ('memo','issues','claims','summary')").bind(run).first<any>();
  if(count.n!==100000||checks.n!==5000||artifacts.n!==4)return json({error:'Saved evidence is incomplete',reviews:count.n,checks:checks.n,artifacts:artifacts.n},409);
  await db.prepare("UPDATE runs SET status='completed',updated_at=? WHERE id=?").bind(new Date().toISOString(),run).run();return json({completed:true,reviews:count.n,checks:checks.n});
 }
 return json({error:'Unknown import type'},400);
 }catch{return json({error:'Invalid import request'},400)}
}
