"""Live Site business API -> outbound GPU worker -> unchanged original model inference."""
from pathlib import Path
import argparse
from urllib.request import Request,build_opener
import hashlib,json,subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from score_api.bailian import NoRedirect
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/web_original_algorithm_20261030/live_http');args=parser.parse_args()
    credentials=json.loads((ROOT/'.score-api/web-worker.json').read_text(encoding='utf8'))
    origin=credentials['site_url'];headers={'OAI-Sites-Authorization':'Bearer '+credentials['site_token'],'X-Inference-Key':credentials['worker_key']}
    opener=build_opener(NoRedirect());folder=args.output;folder.mkdir(parents=True,exist_ok=True)
    def call(method,path,body=None,extra=None):
        request=Request(origin+path,body,{**headers,**(extra or {})},method=method)
        with opener.open(request,timeout=30) as response:return json.load(response)
    deadline=time.monotonic()+90
    while True:
        health=call('GET','/api/recordings/health')
        if health['ready']:break
        if time.monotonic()>deadline:raise RuntimeError('Original inference worker did not become ready')
        time.sleep(3)
    baseline=json.loads((ROOT/'build/bailian_20261030/zuguo_http/http_result.json').read_text(encoding='utf8'))
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/'build/vocal_40s_phrase_20261030/inputs/zuguo/source.wav'),'-ar','44100','-ac','1','-f','f32le','-'])
    sha=hashlib.sha256(raw).hexdigest();assert sha==baseline['source_sha256']
    job=call('POST','/api/recordings',raw,{'Content-Type':'application/octet-stream','X-Audio-Format':'f32le','X-Input-Mode':'vocal',
        'X-Sample-Rate':'44100','X-Audio-SHA256':sha,'Idempotency-Key':uuid.uuid4().hex})
    start=time.monotonic();phase=None
    try:
        while time.monotonic()-start<660:
            job=call('GET','/api/recordings/'+job['job_id'])
            if job['phase']!=phase:phase=job['phase'];print(phase,job['progress'],flush=True)
            if job['status'] in ('succeeded','failed','cancelled'):break
            time.sleep(2)
        (folder/'http_result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
        assert job['status']=='succeeded',job.get('error')
        result=job['result'];assert result['source_sha256']==sha
        assert result['algorithm_id']==health['algorithm_id'] and result['implementation_sha256']==health['implementation_sha256']
        old=baseline['result']['notes'];new=result['notes'];same=[n['midi'] for n in new]==[n['midi'] for n in old]
        onset=max(abs(a['start_ms']-b['start_ms']) for a,b in zip(old,new)) if len(old)==len(new) else None
        duration=max(abs(a['duration_ms']-b['duration_ms']) for a,b in zip(old,new)) if len(old)==len(new) else None
        report={'passed':True,'live_business_http':True,'source_sha256_identical':True,'algorithm_id':result['algorithm_id'],
            'implementation_sha256':result['implementation_sha256'],'notes':len(new),'historical_notes':len(old),
            'same_pitch_sequence':same,'max_onset_delta_ms':onset,'max_duration_delta_ms':duration,
            'seconds':round(time.monotonic()-start,2),'cloud_usage':result.get('cloud_usage',{}),
            'timing':result.get('timing'),'physical_phone_or_fpga_test':False}
        (folder/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
        assert same,'Same implementation ran, but cloud speech observation changed; inspect regression, do not hardcode the song'
        assert onset==0 and duration==0,'Original onset/duration regression changed'
    finally:
        if job['status'] not in ('succeeded','failed','cancelled'):call('DELETE','/api/recordings/'+job['job_id'])
if __name__=='__main__':main()
