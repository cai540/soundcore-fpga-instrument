"""Production Site -> real Qwen image request -> symbolic timing regression."""
from pathlib import Path
from urllib.request import Request,build_opener
from urllib.error import HTTPError
import base64,json,sys,time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from score_api.bailian import NoRedirect
from score_api.sheet import compile_score

def main():
    folder=ROOT/'build/birthday_sheet_20261031/live';folder.mkdir(parents=True,exist_ok=True)
    credential=json.loads((ROOT/'.score-api/web-worker.json').read_text(encoding='utf8'))
    picture=ROOT/'web/phone-lab-20261030/public/sheet-test.png'
    body=json.dumps({'image':'data:image/png;base64,'+base64.b64encode(picture.read_bytes()).decode('ascii')}).encode()
    req=Request(credential['site_url']+'/api/sheet',body,
        {'Content-Type':'application/json','OAI-Sites-Authorization':'Bearer '+credential['site_token'],'X-Inference-Key':credential['worker_key']},method='POST')
    start=time.monotonic()
    try:
        with build_opener(NoRedirect()).open(req,timeout=130) as response:status=response.status;result=json.load(response)
    except HTTPError as error:status=error.code;result=json.load(error)
    # Never save credentials or raw upstream response; just the public contract.
    (folder/'response.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    assert status==200,result.get('error')
    compiled=compile_score(result['score'],bpm=80)
    prior=json.loads((ROOT/'web/phone-lab-20261030/tests/fixtures/sheet_vision_observed.json').read_text(encoding='utf8'))
    actual=[[e['start_ms'],e['duration_ms'],e['midi']] for e in compiled['events']]
    report={'passed':actual==prior['expected_events'],'http_status':status,'seconds':round(time.monotonic()-start,2),
        'notes':result['summary']['notes'],'model':result['model'],'request_id':result.get('request_id'),
        'real_cloud_call':True,'symbolic_pitch_duration_rest_match':actual==prior['expected_events'],
        'tempo_normalized_only_for_comparison':80,'user_birthday_audio_reproduced':False}
    (folder/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    assert report['passed'],'Actual image symbols changed; inspect the model output rather than patching the answer'

if __name__=='__main__':main()
