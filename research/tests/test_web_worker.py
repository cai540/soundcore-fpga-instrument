from array import array
import hashlib,unittest
from score_api.web_worker import run_job,BusinessClient

class WebWorkerTests(unittest.TestCase):
    def case(self):
        raw=array('f',[.1]*4000).tobytes();source={'source_sample_rate':16000,'source_duration_ms':250,'source_sha256':hashlib.sha256(raw).hexdigest(),'request_id':'a'*32,'input_mode':'vocal'}
        return raw,source,{'job_id':'b'*32,'lease':'c'*32,'source':source}
    def test_transport_reuses_the_original_result_without_changing_notes(self):
        raw,source,claim=self.case();result={'schema_version':1,**source,'algorithm_id':'final','notes':[{'start_ms':20,'duration_ms':200,'midi':67}]}
        class Jobs:
            cancelled=False
            def submit(self,body,s):self.body=body;return {'job_id':'local'}
            def get(self,key):return {'status':'succeeded','result':result}
            def cancel(self,key):self.cancelled=True
        class Client:
            found=None
            def call(self,method,path,value=None,**kw):
                if method=='GET':return raw
                self.found=value['result'];return {'ok':True}
        jobs=Jobs();client=Client();run_job(claim,client,jobs,{'algorithm_id':'final','implementation_sha256':'build'},lambda:False)
        self.assertEqual(client.found['notes'],result['notes']);self.assertEqual(jobs.body,raw);self.assertTrue(jobs.cancelled)
    def test_cancellation_cancels_the_original_local_job(self):
        raw,source,claim=self.case()
        class Jobs:
            cancelled=False
            def submit(self,body,s):return {'job_id':'local'}
            def get(self,key):return {'status':'running','progress':40,'phase':'pitch'}
            def cancel(self,key):self.cancelled=True
        class Client:
            def call(self,method,path,value=None,**kw):return raw if method=='GET' else {'cancelled':True}
        jobs=Jobs();run_job(claim,Client(),jobs,{},lambda:False);self.assertTrue(jobs.cancelled)
    def test_credential_transport_refuses_arbitrary_sites_and_http(self):
        for url in ['http://example.com','https://evil.example','https://owned.chatgpt.site@evil.com','https://site.chatgpt.site/path']:
            with self.assertRaises(ValueError):BusinessClient({'site_url':url,'site_token':'token','worker_key':'key'})

if __name__=='__main__':unittest.main()
