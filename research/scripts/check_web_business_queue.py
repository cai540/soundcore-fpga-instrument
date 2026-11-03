"""Local D1/R2 protocol tests; the musical result is explicitly a contract fixture."""
from pathlib import Path
from array import array
import hashlib,http.client,json,uuid

ROOT=Path(__file__).resolve().parents[1]
KEY='test-worker-secret-local-only-20261030'
expected=json.loads((ROOT/'web/phone-lab-20261030/lib/expected-backend.json').read_text())
def call(method,path,body=None,headers=None):
    c=http.client.HTTPConnection('127.0.0.1',5187,timeout=15)
    try:
        c.request(method,path,body,{'X-Inference-Key':KEY,**(headers or {})});r=c.getresponse();raw=r.read()
        return r.status,json.loads(raw) if r.getheader('content-type','').startswith('application/json') else raw
    finally:c.close()
def submit():
    body=array('f',[.1]*4000).tobytes();headers={'Content-Type':'application/octet-stream','X-Audio-Format':'f32le','X-Sample-Rate':'16000',
        'X-Input-Mode':'vocal','X-Audio-SHA256':hashlib.sha256(body).hexdigest(),'Idempotency-Key':uuid.uuid4().hex}
    status,job=call('POST','/api/recordings',body,headers);assert status==202,(status,job)
    status,again=call('POST','/api/recordings',body,headers);assert status==202 and again['job_id']==job['job_id']
    return body,job
def poll(info=None):
    status,claim=call('POST','/api/inference/poll',json.dumps(info or {**expected,'worker_id':'testworker1234567890'}),{'Content-Type':'application/json'})
    return status,claim
def main():
    bad={**expected,'implementation_sha256':'bad','worker_id':'testworker1234567890'}
    assert poll(bad)[0]==403
    assert poll()[0]==200
    assert call('GET','/api/recordings/health')[1]['ready']
    body,job=submit();status,claim=poll();assert status==200 and claim['job_id']==job['job_id']
    assert poll()[1]['job_id'] is None # Atomic claim: not executable twice.
    path='/api/inference/'+job['job_id'];lease={'X-Job-Lease':claim['lease'],'Content-Type':'application/json'}
    assert call('GET',path,headers=lease)[1]==body
    source=claim['source'];wrong={**source,'schema_version':1,**expected,'notes':[{'start_ms':0,'duration_ms':200,'midi':60}],'source_sha256':'wrong'}
    assert call('POST',path,json.dumps({'result':wrong}),lease)[0]==403
    result={**source,'schema_version':1,**expected,'notes':[{'start_ms':0,'duration_ms':200,'midi':60}]}
    assert call('POST',path,json.dumps({'result':result}),lease)[0]==200
    saved=call('GET','/api/recordings/'+job['job_id'])[1];assert saved['status']=='succeeded' and saved['result']==result
    # Completion deletes the temporary R2 audio; the task can no longer be downloaded.
    assert isinstance(call('GET',path,headers=lease)[1],dict)
    _,cancelled=submit();claim=poll()[1];assert claim['job_id']==cancelled['job_id']
    assert call('DELETE','/api/recordings/'+cancelled['job_id'])[0]==200
    response=call('POST','/api/inference/'+cancelled['job_id'],json.dumps({'progress':50,'phase':'pitch'}),{'X-Job-Lease':claim['lease']})
    assert response[1]['cancelled']
    assert call('GET','/api/recordings/'+cancelled['job_id'])[1]['status']=='cancelled'
    print('PASS: local D1/R2 identity, build mismatch, idempotency, atomic claim, wrong-result rejection, completion cleanup and cancellation; model=fixture')
if __name__=='__main__':main()
