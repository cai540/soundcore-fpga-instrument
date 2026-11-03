"""Send a real sheet image through the asynchronous App-facing API."""
from pathlib import Path
import argparse,hashlib,http.client,json,time,uuid

def main():
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--port',type=int,default=8765);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    raw=a.image.read_bytes();sha=hashlib.sha256(raw).hexdigest();token=Path('.score-api/service.key').read_text().strip()
    def call(method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',a.port,timeout=30)
        try:
            c.request(method,path,body=body,headers={'Authorization':'Bearer '+token,**(headers or {})});r=c.getresponse();v=json.loads(r.read());assert r.status in (200,202),(r.status,v);return v
        finally:c.close()
    assert call('GET','/v1/sheet-health')['ready']
    mime='image/png' if raw.startswith(b'\x89PNG') else 'image/jpeg'
    job=call('POST','/v1/sheet-transcriptions',raw,{'Content-Type':mime,'X-Image-SHA256':sha,'Idempotency-Key':uuid.uuid4().hex})
    start=time.monotonic();last=None
    while time.monotonic()-start<610:
        job=call('GET','/v1/sheet-transcriptions/'+job['job_id'])
        if job['phase']!=last:last=job['phase'];print(last,job['progress'],flush=True)
        if job['status'] in ('succeeded','failed','cancelled'):break
        time.sleep(.5)
    (a.output/'http_result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
    assert job['status']=='succeeded',job.get('error')
    print('completed image API',job['result']['summary'],'seconds',round(time.monotonic()-start,2),flush=True)

if __name__=='__main__':main()
