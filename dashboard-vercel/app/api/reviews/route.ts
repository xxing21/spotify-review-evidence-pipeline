import { currentRun,database,intents,json,topics } from '../../../lib/data';
export async function GET(request:Request){try{
 const p=new URL(request.url).searchParams;const topic=p.get('topic')||'',intent=p.get('intent')||'',query=(p.get('q')||'').slice(0,300);
 if(topic&&!topics.includes(topic))return json({error:'Unknown topic'},400);
 if(intent&&intent!=='friction'&&!intents.includes(intent))return json({error:'Unknown intent'},400);
 const run=await currentRun();if(!run)return json({rows:[],total:0});
 const page=Math.max(1,Math.min(5000,Number(p.get('page'))||1));const min=Math.max(1,Math.min(5,Number(p.get('severity'))||1));
 const where=['run_id=?','severity>=?'];const values:any[]=[run.id,min];
 if(topic){if(!topics.includes(topic))return json({error:'Unknown topic'},400);where.push('topic=?');values.push(topic)}
 if(intent==='friction'){where.push("intent IN ('complaint','cancellation')")}else if(intent){if(!intents.includes(intent))return json({error:'Unknown intent'},400);where.push('intent=?');values.push(intent)}
 if(query){where.push("(body LIKE ? ESCAPE '\\' OR id=?)");values.push('%'+query.replace(/[\\%_]/g,'\\$&')+'%',query)}
 const condition=where.join(' AND ');const [count,result]=await Promise.all([
 database().prepare('SELECT COUNT(*) AS total FROM reviews WHERE '+condition).bind(...values).first<any>(),
 database().prepare('SELECT * FROM reviews WHERE '+condition+' ORDER BY severity DESC,id ASC LIMIT 20 OFFSET ?').bind(...values,(page-1)*20).all<any>()]);
 return json({rows:result.results.map((r:any)=>({...r,entities:JSON.parse(r.entities),source:JSON.parse(r.source)})),total:count.total,page,page_size:20});
 }catch{return json({error:'Review query failed'},503)}}
