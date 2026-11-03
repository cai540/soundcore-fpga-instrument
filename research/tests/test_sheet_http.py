from pathlib import Path
import hashlib,http.client,io,json,sys,tempfile,threading,time,unittest,uuid
from PIL import Image
from score_api.jobs import Jobs
from score_api.server import make_server
from test_sheet import sample

class SheetHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.slow=False
        (self.root/'config.json').write_text('{}')
        def command(folder):
            script=folder/'fixture.py'
            source="""import json,time,hashlib
from pathlib import Path
p=Path(__file__).parent;s=json.loads((p/'source.json').read_text());assert hashlib.sha256((p/'image.bin').read_bytes()).hexdigest()==s['source_sha256']
print('SCORE_API:'+json.dumps({'event':'progress','phase':'reading_sheet','progress':20}),flush=True)
"""
            if self.slow:source+='time.sleep(10)\n'
            result={'schema_version':1,'algorithm_id':'test-sheet-fixture','score':sample()}
            source+='r='+repr(result)+"\nr.update(s)\nprint('SCORE_API:'+json.dumps({'event':'result','result':r}),flush=True)\n"
            script.write_text(source,encoding='utf8');return [sys.executable,'-u',str(script)]
        self.jobs=Jobs(self.root/'config.json',self.root/'work',command=command,capacity=1)
        self.token='local-test-token-no-real-key-123456'
        self.server=make_server(('127.0.0.1',0),self.token,self.jobs,sheet_ready=lambda:True)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        out=io.BytesIO();Image.new('RGB',(128,128),'white').save(out,format='PNG');self.image=out.getvalue()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.jobs.close();self.tmp.cleanup()
    def call(self,method,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            c.request(method,path,body,{'Authorization':'Bearer '+self.token,**(headers or {})});r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()
    def post(self,id=None):return self.call('POST','/v1/sheet-transcriptions',self.image,{'Content-Type':'image/png',
        'Idempotency-Key':id or uuid.uuid4().hex,'X-Image-SHA256':hashlib.sha256(self.image).hexdigest()})
    def wait(self,id):
        end=time.monotonic()+5
        while time.monotonic()<end:
            _,j=self.call('GET','/v1/sheet-transcriptions/'+id)
            if j['status'] in ('succeeded','failed','cancelled'):return j
            time.sleep(.02)
        self.fail('timeout')
    def test_image_request_reaches_worker_validates_and_does_not_enter_audio_pipeline(self):
        self.assertTrue(self.call('GET','/v1/sheet-health')[1]['ready'])
        key=uuid.uuid4().hex;status,job=self.post(key);self.assertEqual(status,202)
        self.assertEqual(self.post(key)[1]['job_id'],job['job_id'])
        result=self.wait(job['job_id']);self.assertEqual(result['status'],'succeeded')
        self.assertEqual(result['result']['score'],sample());self.assertEqual(result['input_mode'],'sheet')
        self.assertEqual(self.call('GET','/v1/transcriptions/'+job['job_id'])[0],404)
        self.assertEqual(result['result']['source_sha256'],hashlib.sha256(self.image).hexdigest())
    def test_cancelled_image_never_replaces_a_later_result(self):
        self.slow=True;_,old=self.post()
        self.assertEqual(self.call('DELETE','/v1/sheet-transcriptions/'+old['job_id'])[1]['status'],'cancelled')
        self.slow=False;_,new=self.post();self.assertEqual(self.wait(new['job_id'])['status'],'succeeded')
        self.assertIsNone(self.wait(old['job_id'])['result'])

if __name__=='__main__':unittest.main()
