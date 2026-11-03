from pathlib import Path
import json,sys,tempfile,time,unittest
from score_api.jobs import Jobs
from score_api.resident_process import ResidentProcess
from score_api.protocol import audio_request
from array import array
import hashlib,uuid

FAKE='''import json,os,sys,time
def emit(event,**kw):print('SCORE_API:'+json.dumps(dict(event=event,**kw)),flush=True)
emit('ready',preload={'pid':os.getpid()})
for line in sys.stdin:
 c=json.loads(line);s=json.loads(__import__('pathlib').Path(c['directory'],'source.json').read_text());j=c['job_id']
 emit('progress',job_id=j,phase='speech',progress=10)
 if s.get('request_id')=='0'*32:time.sleep(10)
 r=dict(schema_version=1,**s,notes=[dict(start_ms=10,duration_ms=100,midi=60)],worker_pid=os.getpid())
 emit('result',job_id=j,result=r);emit('done',job_id=j,healthy=True)
'''

class ResidentProcessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.config=self.root/'config.json';self.config.write_text('{}')
  self.script=self.root/'fake.py';self.script.write_text(FAKE)
  self.jobs=Jobs(self.config,self.root/'jobs',resident=True,idle_s=30)
  self.jobs.resident.command=[sys.executable,'-u',str(self.script)]
  self.raw=array('f',[.1]*4000).tobytes()
 def tearDown(self):self.jobs.close();self.temp.cleanup()
 def submit(self,key=None):
  source=audio_request(self.raw,16000,key or uuid.uuid4().hex,hashlib.sha256(self.raw).hexdigest(),'vocal')
  return self.jobs.submit(self.raw,source)['job_id']
 def wait(self,key):
  deadline=time.monotonic()+5
  while time.monotonic()<deadline:
   state=self.jobs.get(key)
   if state['status'] in ('succeeded','failed','cancelled'):return state
   time.sleep(.01)
  self.fail('Job timeout')
 def test_two_tasks_reuse_one_process_and_keep_sources_distinct(self):
  ready=self.jobs.preload().result(timeout=5)
  a=self.wait(self.submit());b=self.wait(self.submit())
  self.assertEqual(a['status'],'succeeded');self.assertEqual(b['status'],'succeeded')
  self.assertEqual(a['result']['worker_pid'],ready['pid']);self.assertEqual(b['result']['worker_pid'],ready['pid'])
  self.assertNotEqual(a['result']['request_id'],b['result']['request_id'])
 def test_cancel_running_restarts_process_without_old_result(self):
  old=self.jobs.preload().result(timeout=5)['pid'];key=self.submit('0'*32)
  deadline=time.monotonic()+3
  while self.jobs.get(key)['phase']!='speech' and time.monotonic()<deadline:time.sleep(.01)
  self.jobs.cancel(key);fresh=self.wait(self.submit())
  self.assertEqual(fresh['status'],'succeeded');self.assertNotEqual(fresh['result']['worker_pid'],old)
  self.assertIsNone(self.jobs.get(key)['result'])
 def test_idle_releases_process_and_next_task_reloads(self):
  self.jobs.resident.idle_s=.1
  old=self.jobs.preload().result(timeout=5)['pid'];deadline=time.monotonic()+3
  while self.jobs.resident.process is not None and time.monotonic()<deadline:time.sleep(.02)
  self.assertIsNone(self.jobs.resident.process)
  new=self.wait(self.submit());self.assertEqual(new['status'],'succeeded');self.assertNotEqual(old,new['result']['worker_pid'])
 def test_cancel_queued_task_does_not_kill_active_process(self):
  old=self.jobs.preload().result(timeout=5)['pid'];a=self.submit('0'*32);b=self.submit()
  self.jobs.cancel(b);self.assertEqual(self.jobs.resident.process.pid,old)
  self.jobs.cancel(a);self.assertEqual(self.jobs.get(b)['status'],'cancelled')
 def test_silent_startup_times_out_and_is_cleaned_up(self):
  child=ResidentProcess(self.config,startup_s=.1,command=[sys.executable,'-c','import time;time.sleep(10)'])
  try:
   with self.assertRaises(TimeoutError):child.preload()
   self.assertIsNone(child.process)
  finally:child.close()

if __name__=='__main__':unittest.main()
