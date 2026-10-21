import { database,json } from '../../../lib/data';
export async function GET(){try{await database().prepare('SELECT 1 AS ok').first();return json({ok:true,database:'connected',model_calls:0})}catch{return json({ok:false,database:'unavailable'},503)}}
