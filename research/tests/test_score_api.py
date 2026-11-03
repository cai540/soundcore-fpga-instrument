from array import array
from pathlib import Path
import hashlib, http.client, json, math, sys, tempfile, threading, time, unittest, uuid
from score_api.jobs import Jobs
from score_api.server import make_server
from score_api.protocol import ApiError, audio_request, validate_result

TOKEN = 'test-service-token-not-a-real-secret'


class ScoreApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'config.json').write_text('{}')
        self.slow = False
        def command(folder):
            script = folder/'fake_model.py'
            script.write_text("""import json,time
from pathlib import Path
s=json.loads(Path(__file__).with_name('source.json').read_text())
print('SCORE_API:'+json.dumps({'event':'progress','phase':'speech','progress':30}),flush=True)
""" + ('time.sleep(10)\n' if self.slow else '') + """r={'schema_version':1,**s,'algorithm_id':'test-model','notes':[{'start_ms':10,'duration_ms':100,'midi':60},{'start_ms':150,'duration_ms':100,'midi':62}]}
print('SCORE_API:'+json.dumps({'event':'result','result':r}),flush=True)
""", encoding='utf8')
            return [sys.executable, '-u', str(script)]
        self.jobs = Jobs(self.root/'config.json', self.root/'work', command=command, capacity=1)
        self.server = make_server(('127.0.0.1',0),TOKEN,self.jobs)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.body = array('f',[.1]*4000).tobytes()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.jobs.close();self.temp.cleanup()

    def call(self, method, path, body=None, headers=None, auth=True):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        h={'Authorization':'Bearer '+TOKEN} if auth else {}
        h.update(headers or {})
        try:
            c.request(method,path,body=body,headers=h);r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()

    def submit(self, body=None, key=None):
        data=self.body if body is None else body
        return self.call('POST','/v1/transcriptions',data,{'Content-Type':'application/octet-stream',
            'X-Audio-Format':'f32le','X-Sample-Rate':'16000','X-Input-Mode':'vocal',
            'X-Audio-SHA256':hashlib.sha256(data).hexdigest(),'Idempotency-Key':key or uuid.uuid4().hex})

    def wait(self, key):
        until=time.monotonic()+5
        while time.monotonic()<until:
            status,result=self.call('GET','/v1/transcriptions/'+key)
            if result['status'] in ('succeeded','failed','cancelled'):return result
            time.sleep(.02)
        self.fail('Job did not finish')

    def test_authentication_is_required_and_health_has_no_accuracy_claim(self):
        self.assertEqual(self.call('GET','/v1/health',auth=False)[0],401)
        status,health=self.call('GET','/v1/health')
        self.assertEqual(status,200);self.assertFalse(health['accuracy_claimed'])
        self.assertNotIn(TOKEN,json.dumps(health))

    def test_real_http_job_preserves_source_times_and_repeated_request_id(self):
        key=uuid.uuid4().hex;status,job=self.submit(key=key);self.assertEqual(status,202)
        status,again=self.submit(key=key);self.assertEqual(again['job_id'],job['job_id'])
        result=self.wait(job['job_id']);self.assertEqual(result['status'],'succeeded')
        self.assertEqual(result['result']['notes'][0]['start_ms'],10)
        self.assertEqual(result['result']['source_sha256'],hashlib.sha256(self.body).hexdigest())
        self.assertEqual(self.submit(body=array('f',[.2]*4000).tobytes(),key=key)[0],409)

    def test_cancel_running_process_frees_capacity_and_discards_result(self):
        self.slow=True;_,job=self.submit()
        until=time.monotonic()+3
        while self.jobs.items[job['job_id']].process is None and time.monotonic()<until:time.sleep(.01)
        self.assertEqual(self.submit()[0],429)
        status,cancelled=self.call('DELETE','/v1/transcriptions/'+job['job_id'])
        self.assertEqual(status,200);self.assertEqual(cancelled['status'],'cancelled')
        self.assertIsNone(cancelled['result'])
        self.slow=False;status,new=self.submit();self.assertEqual(status,202)
        self.assertEqual(self.wait(new['job_id'])['status'],'succeeded')

    def test_bad_float_silence_wrong_hash_and_instrument_are_rejected(self):
        key=uuid.uuid4().hex
        for data in (array('f',[0]*4000).tobytes(),array('f',[math.nan]*4000).tobytes()):
            self.assertEqual(self.submit(data)[0],422)
        with self.assertRaises(ApiError):audio_request(self.body,16000,key,'wrong','vocal')
        with self.assertRaises(ApiError):audio_request(self.body,16000,key,hashlib.sha256(self.body).hexdigest(),'instrument')

    def test_result_validation_refuses_cross_job_overlap_and_fractional_midi(self):
        source=audio_request(self.body,16000,uuid.uuid4().hex,hashlib.sha256(self.body).hexdigest(),'vocal')
        result={'schema_version':1,**source,'notes':[{'start_ms':0,'duration_ms':100,'midi':60}]}
        self.assertIs(validate_result(result,source),result)
        for altered in ({**result,'source_sha256':'another'},
                        {**result,'notes':[{'start_ms':0,'duration_ms':100,'midi':60.5}]},
                        {**result,'notes':[{'start_ms':0,'duration_ms':100,'midi':60},{'start_ms':90,'duration_ms':50,'midi':62}]}):
            with self.assertRaises(ApiError):validate_result(altered,source)


if __name__=='__main__':unittest.main()
