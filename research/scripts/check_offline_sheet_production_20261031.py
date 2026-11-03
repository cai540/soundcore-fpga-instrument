"""Read-only private-Site smoke test. No credential values are printed or persisted."""
from pathlib import Path
from urllib.request import Request,build_opener
from urllib.error import HTTPError
import json,hashlib,re,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from score_api.bailian import NoRedirect
cfg=json.loads((ROOT/'.score-api/web-worker.json').read_text(encoding='utf-8'))
origin='https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site'
assert cfg['site_url'].rstrip('/')==origin
headers={'OAI-Sites-Authorization':'Bearer '+cfg['site_token'],'X-Inference-Key':cfg['worker_key'],'Content-Type':'application/json'}
opener=build_opener(NoRedirect())
def call(path,body=None):
    request=Request(origin+path,body,headers,method='POST'if body is not None else'GET')
    try:
        with opener.open(request,timeout=60)as response:return response.status,response.read()
    except HTTPError as error:return error.code,error.read()

status,body=call('/api/sheet',b'{"image":"not-uploaded"}')
assert status==410 and json.loads(body)['code']=='local_fpga_required'
out={'image_api':{'status':status,'retired':True},'ocr_assets':{}}
for name in ['tesseract.min.js','lang/chi_sim.traineddata']:
    status,body=call('/offline/ocr/'+name)
    expected=hashlib.sha256((ROOT/'web/phone-lab-20261030/public/offline/ocr'/name).read_bytes()).hexdigest()
    assert status==200 and hashlib.sha256(body).hexdigest()==expected
    out['ocr_assets'][name]={'status':status,'bytes':len(body),'sha256_verified':True}
status,body=call('/api/recordings/health');health=json.loads(body)
assert status==200 and health['implementation_sha256']=='2dfe5b053b77fdc61b0eb44a0a2e76abf8d5e543325e222135eb617d07ce5238'
out['recording_backend']={'status':status,'ready':health['ready'],'implementation_sha256':health['implementation_sha256']}
status,body=call('/');assert status==200
assets=set(re.findall(r'(?:src|href)="(/_next/static/chunks/[^"\s]+\.js)"',body.decode('utf-8')))
bundles={}
for path in assets:
    code,data=call(path)
    if code==200:bundles[path]=data
for path,data in list(bundles.items()):
    for child in re.findall(rb'(?:(?:\./)|(?:/_next/static/chunks/))([A-Za-z0-9_.-]+\.js)',data):
        target='/_next/static/chunks/'+child.decode()
        if target not in bundles:
            code,value=call(target)
            if code==200:bundles[target]=value
assert any('FPGA 离线识谱'.encode()in b for b in bundles.values()),'New client not confirmed'
out['published_client']={'status':200,'bundles':len(bundles),'offline_ui_confirmed':True}
target=ROOT/'build/offline_ocr_20261031/production_validation.json'
target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out))
