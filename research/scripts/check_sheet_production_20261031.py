from pathlib import Path
from urllib.request import Request,build_opener
from urllib.error import HTTPError
import json,base64,hashlib,time,subprocess,sys,os
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));from score_api.bailian import NoRedirect
folder=root/'build/sheet_acceptance_20261031';credential=json.loads((root/'.score-api/web-worker.json').read_text(encoding='utf8'))
assert credential['site_url'].rstrip('/')=='https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site'
headers={'OAI-Sites-Authorization':'Bearer '+credential['site_token'],'X-Inference-Key':credential['worker_key'],'Content-Type':'application/json'}
opener=build_opener(NoRedirect());results={}
def call(path,body=None):
 request=Request(credential['site_url']+path,None if body is None else json.dumps(body,ensure_ascii=False).encode('utf8'),headers,method='GET' if body is None else'POST')
 with opener.open(request,timeout=130)as response:return response.status,json.load(response)
health_status,health=call('/api/recordings/health');results['recording_backend']={'http_status':health_status,'ready':health.get('ready'),'algorithm_id':health.get('algorithm_id'),'implementation_sha256':health.get('implementation_sha256')}
assert health['ready'] and health['implementation_sha256']=='2dfe5b053b77fdc61b0eb44a0a2e76abf8d5e543325e222135eb617d07ce5238'
row=json.loads((folder/'pixel_runs/zuguo_row_1.json').read_text(encoding='utf8'));command={'op':'contact','file':str(folder/'inputs/zuguo.jpg'),'line':row['line']}
output=subprocess.check_output([sys.executable,str(root/'scripts/sheet_model_bridge.py')],input=json.dumps(command).encode('utf8'),cwd=root,env={**os.environ,'PYTHONIOENCODING':'utf-8'})
image=json.loads(output)['detailImage'];sha=hashlib.sha256(image.encode('utf8')).hexdigest();start=time.monotonic()
status,data=call('/api/sheet',{'image':image,'action':'digits','context':{'candidate_count':16},'source_sha256':sha})
(folder/'production-digits-response.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
expected=json.loads((folder/'manual_first_rows.json').read_text(encoding='utf8'))['samples']['zuguo']['degree'];assert status==200 and data['source_sha256']==sha and data['digits']==expected
results['digits']={'http_status':status,'real_cloud_call':True,'seconds':round(time.monotonic()-start,2),'digits_match':True,'source_match':True,'count':len(data['digits']),'request_id':data.get('request_id')}
image='data:image/jpeg;base64,'+base64.b64encode((folder/'inputs/zuguo.jpg').read_bytes()).decode();sha=hashlib.sha256(image.encode()).hexdigest()
header_command={'op':'crop','file':str(folder/'inputs/zuguo.jpg'),'line':{'top':0,'bottom':(row['line']['top']+5)/1586*1000}}
header=json.loads(subprocess.check_output([sys.executable,str(root/'scripts/sheet_model_bridge.py')],input=json.dumps(header_command).encode(),cwd=root,env={**os.environ,'PYTHONIOENCODING':'utf-8'}))['image'];start=time.monotonic()
status,data=call('/api/sheet',{'image':image,'action':'layout','detailImage':header,'source_sha256':sha});layout=data['layout']
(folder/'production-layout-response.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');assert status==200 and layout['tonic_midi']==63 and [6,8]in layout['meter_options']and[9,8]in layout['meter_options']
results['header']={'http_status':status,'real_cloud_call':True,'seconds':round(time.monotonic()-start,2),'tonic_midi':layout['tonic_midi'],'meter_options':layout['meter_options'],'request_id':data.get('request_id')}
(folder/'production-validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(results,ensure_ascii=False))
