"""Submit real PCM over HTTP; no saved answer is given to the service."""
from pathlib import Path
import argparse, csv, hashlib, http.client, json, subprocess, time, uuid


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--audio',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--rate',type=int,default=44100)
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--token-file',type=Path,default=Path('.score-api/service.key'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(a.audio),'-ar',str(a.rate),'-ac','1','-f','f32le','-'])
    digest=hashlib.sha256(raw).hexdigest();token=a.token_file.read_text().strip()
    def call(method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',a.port,timeout=30)
        try:
            c.request(method,path,body=body,headers={'Authorization':'Bearer '+token,**(headers or {})})
            r=c.getresponse();v=json.loads(r.read());assert r.status in (200,202),(r.status,v);return v
        finally:c.close()
    health=call('GET','/v1/health');assert health['ready']
    job=call('POST','/v1/transcriptions',raw,{'Content-Type':'application/octet-stream','X-Audio-Format':'f32le',
        'X-Sample-Rate':str(a.rate),'X-Input-Mode':'vocal','X-Audio-SHA256':digest,'Idempotency-Key':uuid.uuid4().hex})
    start=time.monotonic();phase=None
    while time.monotonic()-start<660:
        job=call('GET','/v1/transcriptions/'+job['job_id'])
        if job['phase']!=phase:
            phase=job['phase'];print(phase,job['progress'],flush=True)
        if job['status'] in ('failed','cancelled','succeeded'):break
        time.sleep(.5)
    (a.output/'http_result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
    assert job['status']=='succeeded',job.get('error')
    result=job['result'];assert result['source_sha256']==digest
    with (a.output/'notes.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.writer(f);w.writerow(['start_ms','duration_ms','midi'])
        for n in result['notes']:w.writerow([n['start_ms'],n['duration_ms'],n['midi']])
    print('completed real HTTP inference',len(result['notes']),'notes',round(time.monotonic()-start,2),'seconds',flush=True)


if __name__=='__main__':main()
