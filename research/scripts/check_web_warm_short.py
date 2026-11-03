"""Measure a second, 15-second real business request; no prerecorded answer."""
from pathlib import Path
from urllib.request import Request,build_opener
import hashlib,json,subprocess,sys,time,uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from score_api.bailian import NoRedirect
from score_api.protocol import validate_result

def main():
    credentials=json.loads((ROOT/'.score-api/web-worker.json').read_text(encoding='utf8'))
    headers={'OAI-Sites-Authorization':'Bearer '+credentials['site_token'],'X-Inference-Key':credentials['worker_key']}
    opener=build_opener(NoRedirect());folder=ROOT/'build/warm_models_20261030/live_short';folder.mkdir(parents=True,exist_ok=True)
    def call(method,path,body=None,extra=None):
        req=Request(credentials['site_url']+path,body,{**headers,**(extra or {})},method=method)
        with opener.open(req,timeout=30) as r:return json.load(r)
    health=call('GET','/api/recordings/health');assert health['ready']
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/'build/vocal_40s_phrase_20261030/inputs/zuguo/source.wav'),'-t','15','-ar','44100','-ac','1','-f','f32le','-'])
    source={'source_sha256':hashlib.sha256(raw).hexdigest(),'source_sample_rate':44100,'source_duration_ms':15000,'request_id':uuid.uuid4().hex,'input_mode':'vocal'}
    start=time.monotonic()
    job=call('POST','/api/recordings',raw,{'Content-Type':'application/octet-stream','X-Audio-Format':'f32le','X-Input-Mode':'vocal',
        'X-Sample-Rate':'44100','X-Audio-SHA256':source['source_sha256'],'Idempotency-Key':source['request_id']})
    uploaded=time.monotonic()-start;phase=None
    try:
        while time.monotonic()-start<180:
            job=call('GET','/api/recordings/'+job['job_id'])
            if job['phase']!=phase:phase=job['phase'];print(phase,job['progress'],flush=True)
            if job['status'] in ('succeeded','failed','cancelled'):break
            time.sleep(1)
        (folder/'result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
        assert job['status']=='succeeded',job.get('error')
        result=validate_result(job['result'],source)
        assert result['implementation_sha256']==health['implementation_sha256']
        assert result['timing']['new_model_loads']=={} and result['timing']['segmenter_resets']>=1
        report={'passed':True,'source_duration_ms':15000,'seconds_including_post_upload':round(time.monotonic()-start,2),
            'upload_seconds':round(uploaded,2),'notes':len(result['notes']),'timing':result['timing'],'physical_phone_test':False,
            'accuracy_claimed':False,'observations_cache_reuse_not_assumed':True}
        (folder/'result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
        (folder/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
    finally:
        if job['status'] not in ('succeeded','failed','cancelled'):call('DELETE','/api/recordings/'+job['job_id'])

if __name__=='__main__':main()
