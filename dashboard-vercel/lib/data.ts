import { neon } from '@neondatabase/serverless';
const numeric=new Set(['n','total','completed','checked','cache_reuses','complaints','needs_review','complaint_count','severity_sum']);
function normalize<T>(rows:any[]):T[]{return rows.map(row=>Object.fromEntries(Object.entries(row).map(([k,v])=>[k,numeric.has(k)&&typeof v==='string'?Number(v):v]))) as T[]}
export function database(){
 const url=process.env.DATABASE_URL;if(!url)throw new Error('Saved-data database is not configured');
 const sql=neon(url);
 class Statement{
  constructor(readonly text:string,readonly values:any[]=[]){ }
  bind(...values:any[]){return new Statement(this.text,values)}
  query(){let i=0;return sql.query(this.text.replace(/\?/g,()=>'$'+(++i)),this.values)}
  async all<T=any>(){return {results:normalize<T>(await this.query())}}
  async first<T=any>():Promise<T|null>{return (await this.all<T>()).results[0]??null}
  async run(){await this.query();return {success:true}}
 }
 return {prepare:(text:string)=>new Statement(text),batch:(statements:Statement[])=>sql.transaction(statements.map(s=>s.query()))};
}
export const topics=['access','usability','playback','downloads','catalog','billing','support','other'];
export const intents=['cancellation','complaint','request','praise','unclear'];
export function json(data:unknown,status=200){return Response.json(data,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})}
export async function currentRun(){return database().prepare('SELECT * FROM runs ORDER BY updated_at DESC LIMIT 1').first<any>()}
export async function artifact(run:string,name:string){const r=await database().prepare('SELECT value FROM artifacts WHERE run_id=? AND name=?').bind(run,name).first<any>();return r?JSON.parse(r.value):null}
