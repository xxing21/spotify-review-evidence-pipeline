import getpass,json,subprocess
from pathlib import Path
values=json.loads(getpass.getpass('Deployment credentials JSON (hidden): '))
for key,target,value,sensitive in [('DATABASE_URL','production,preview',values['production_url'],True),('IMPORT_TOKEN','production,preview',values['import_token'],True),('DATABASE_URL','development',values['development_url'],False),('IMPORT_TOKEN','development',values['import_token'],False)]:
 command=['vercel','--scope','xr14','env','add',key,target,'--force','--yes','--sensitive' if sensitive else '--no-sensitive']
 result=subprocess.run(command,input=value,text=True,capture_output=True)
 if result.returncode:
  print('Environment configuration failed for',key,target,'with exit',result.returncode)
  raise SystemExit(result.returncode)
 print('Configured',key,'for',target,flush=True)
result=subprocess.run(['vercel','--scope','xr14','env','pull','.env.local','--yes'],capture_output=True,text=True)
if result.returncode:raise SystemExit('Environment pull failed; values omitted')
present={line.split('=',1)[0].strip() for line in Path('.env.local').read_text().splitlines() if '=' in line and not line.startswith('#')}
required={'DATABASE_URL','IMPORT_TOKEN'}
if not required<=present:raise SystemExit('Missing required environment keys')
print('Required local keys present: DATABASE_URL, IMPORT_TOKEN; values omitted.',flush=True)
