import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const {rows,ranking}=JSON.parse(fs.readFileSync(new URL('../../artifacts/dashboard/development_fixture.json',import.meta.url),'utf8'));
const base='http://127.0.0.1:3000';
async function get(path){const response=await fetch(base+path);assert.equal(response.status,200);return response.json()}
async function post(payload){const response=await fetch(base+'/api/import',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+process.env.IMPORT_TOKEN},body:JSON.stringify(payload)});assert.equal(response.status,200);return response.json()}
assert.equal((await get('/api/health')).database,'connected');
assert.equal((await fetch(base+'/api/import',{method:'POST',body:'{}'})).status,401);
assert.equal((await fetch(base+'/api/reviews?topic=foreign')).status,400);
await post({type:'run',run_id:'production-100k-v1',target:100000,metadata:{scope:'development branch; actual 200-record snapshot'}});
for(let i=0;i<rows.length;i+=100)await post({type:'reviews',rows:rows.slice(i,i+100)});
await post({type:'reviews',rows:rows.slice(0,100)});
const summary=await get('/api/summary');assert.equal(summary.completed,rows.length);
for(let i=0;i<ranking.length;i++){for(const key of ['rank','issue_id','complaint_count','severity_sum','priority_score','mean_severity'])assert.equal(summary.ranking[i][key],ranking[i][key])}
const page1=await get('/api/reviews?page=1'),page2=await get('/api/reviews?page=2');
assert.equal(page1.rows.length,20);assert.equal(page2.rows.length,20);assert.equal(new Set([...page1.rows,...page2.rows].map(r=>r.id)).size,40);
for(const r of page1.rows){const canonical=JSON.stringify(['review_id','review_text','review_rating','review_likes','app_version','review_timestamp'].map(k=>r.source[k]));assert.equal(createHash('sha256').update(canonical).digest('hex'),r.source_hash);assert.equal(r.body,r.source.review_text);assert.ok(r.body.includes(r.evidence))}
const friction=await get('/api/reviews?topic=playback&intent=friction');assert.ok(friction.rows.every(r=>r.topic==='playback'&&['complaint','cancellation'].includes(r.intent)));
const injection=await get('/api/reviews?q='+encodeURIComponent("%_' OR 1=1 -- invalid-label-test"));assert.equal(injection.total,0);
const report={saved_at:new Date().toISOString(),passed:true,actual_review_snapshot:200,database_branch:'dashboard-schema-validation',health:true,unauthorized_import_rejected:true,invalid_topic_rejected:true,idempotent_import:true,rankings_equal_offline:true,pagination_unique:true,source_hashes_valid:true,negative_intent_filter:true,sql_injection_literal:true,model_calls:0};
fs.mkdirSync('../evals/dashboard',{recursive:true});fs.writeFileSync('../evals/dashboard/neon_local_e2e.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
