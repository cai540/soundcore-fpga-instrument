"""Authenticated production smoke test; credentials stay inside the process."""
from pathlib import Path
from urllib.request import Request,build_opener
import json,hashlib,subprocess,sys,os,time,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from score_api.bailian import NoRedirect

credential=json.loads((ROOT/'.score-api/web-worker.json').read_text(encoding='utf8'))
origin='https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site'
assert credential['site_url'].rstrip('/')==origin
headers={'OAI-Sites-Authorization':'Bearer '+credential['site_token'],'X-Inference-Key':credential['worker_key'],'Content-Type':'application/json'}
opener=build_opener(NoRedirect())
def call(path,body=None):
    req=Request(origin+path,None if body is None else json.dumps(body).encode(),headers,method='GET' if body is None else 'POST')
    with opener.open(req,timeout=130)as response:return response.status,response.read()

health_status,body=call('/api/recordings/health');health=json.loads(body)
assert health_status==200 and health['implementation_sha256']=='2dfe5b053b77fdc61b0eb44a0a2e76abf8d5e543325e222135eb617d07ce5238'
result={'recording_backend':dict(status=health_status,ready=health['ready'],implementation_sha256=health['implementation_sha256'])}
source=ROOT/'build/phrase_rest_fix_20261031'
evidence=json.loads((source/'pixel_runs/lantingxu_p2_row_4.json').read_text(encoding='utf8'))
command={'op':'contact','file':str(ROOT/'build/sheet_acceptance_20261031/inputs/lantingxu_p2.jpg'),'line':evidence['line']}
images=json.loads(subprocess.check_output([sys.executable,str(ROOT/'scripts/sheet_model_bridge.py')],input=json.dumps(command).encode(),cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'}))
image=images['detailImage'];identity=hashlib.sha256(image.encode()).hexdigest();start=time.monotonic()
status,body=call('/api/sheet',{'image':image,'action':'digits','context':{'candidate_count':len(evidence['digits'])},'source_sha256':identity})
data=json.loads(body)
assert status==200 and data['source_sha256']==identity and data['digits']==[0,5,3,5]
result['rest_digits']=dict(status=status,digits=data['digits'],source_match=True,real_cloud_call=True,seconds=round(time.monotonic()-start,2),request_id=data.get('request_id'))
status,body=call('/');assert status==200
home=body.decode('utf8');assets=set(re.findall(r'(?:src|href)="(/_next/static/chunks/[^"\s]+\.js)"',home))
bundles={}
for asset in assets:
    _,body=call(asset);bundles[asset]=body
# Vinext can preload secondary client chunks from the entrypoint module.
for asset,body in list(bundles.items()):
    for child in re.findall(rb'(?:(?:\./)|(?:/_next/static/chunks/))([A-Za-z0-9_.-]+\.js)',body):
        target='/_next/static/chunks/'+child.decode()
        if target not in bundles:
            s,b=call(target)
            if s==200:bundles[target]=b
result['published_client']=dict(status=status,loaded_bundles=len(bundles),new_cache_version=any(b'sheet-pixels-v5' in b for b in bundles.values()))
assert result['published_client']['new_cache_version'],'New browser bundle was not confirmed'
for attempt in range(12):
    status,body=call('/api/recordings/health');health=json.loads(body)
    result['recording_backend']['ready']=health['ready']
    if health['ready']:break
    time.sleep(3)
(source/'production-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result))
assert result['recording_backend']['ready'],'Recording worker is still unavailable'
