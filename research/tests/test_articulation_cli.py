"""End-to-end provenance and timing-only export contract."""
from dataclasses import asdict
from pathlib import Path
import csv,json,os,subprocess,sys,tempfile,unittest
import numpy as np
from soundcore_audio.articulation import CarrierConfig
from tools.decode_vocal_carriers import POLICY

ROOT=Path(__file__).resolve().parents[1]

class ArticulationCliTests(unittest.TestCase):
    def run_case(self,parent):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            meta={'unit_source':'automatic-source-audio','units':['a','b'],
                  'pause_after':[0,1,2],'typical_duration_s':.2,'source_sha256':'recording-one'}
            carrier=np.full((3,128),.001);carrier[0,60]=.99;carrier[2,62]=.99
            np.savez(root/'graph.npz',policy=POLICY,metadata=json.dumps(meta),cuts=[0,20,40,60],
                edges=[[0,1],[1,2],[2,3]],carrier=carrier,voiced=[.99,.001,.99],
                boundary_cost=np.zeros(4),phone_likelihood=np.ones((2,3)),
                pitch_boundary=np.full(4,.99),pitch_prior=np.ones(128))
            (root/'config.json').write_text(json.dumps(asdict(CarrierConfig())),encoding='utf8')
            (root/'parent.json').write_text(json.dumps(parent),encoding='utf8')
            env={**os.environ,'PYTHONIOENCODING':'utf-8'}
            result=subprocess.run([sys.executable,'-m','tools.decode_vocal_carriers',
                '--evidence',str(root/'graph.npz'),'--config',str(root/'config.json'),
                '--lock-pitch-input',str(root/'parent.json'),'--output',str(root/'out')],
                cwd=ROOT,env=env,capture_output=True,text=True)
            rows=[]
            if (root/'out/notes.csv').exists():
                with (root/'out/notes.csv').open(encoding='utf8',newline='') as stream:
                    rows=list(csv.DictReader(stream))
            details=json.loads((root/'out/characters.json').read_text()) if (root/'out/characters.json').exists() else None
            return result,rows,details

    def parent(self):
        return {'source_pcm_sha256':'recording-one','units':[
            {'recognized_unit':'a','notes':[{'midi':60}]},
            {'recognized_unit':'b','notes':[{'midi':62}]}]}

    def test_timing_export_keeps_pitch_order_and_real_rest(self):
        result,rows,details=self.run_case(self.parent())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([(int(n['start_ms']),int(n['duration_ms']),int(n['midi'])) for n in rows],
                         [(0,200,60),(400,200,62)])
        self.assertTrue(details['pitch_path_locked'])
        self.assertFalse(details['accepted'])
        self.assertEqual(len(details['pitch_parent_sha256']),64)

    def test_wrong_recording_or_unit_order_cannot_export(self):
        first=self.parent();first['source_pcm_sha256']='another-recording'
        second=self.parent();second['units'].reverse()
        for parent,reason in [(first,'another recording'),(second,'different source unit sequence')]:
            result,rows,details=self.run_case(parent)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(reason,result.stderr)
            self.assertEqual(rows,[])
            self.assertIsNone(details)

if __name__=='__main__':unittest.main()
