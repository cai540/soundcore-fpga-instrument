"""Real inference sanity, not a musical quality acceptance test."""
from pathlib import Path
import json,time,numpy as np
from game_vocal_engine import GameOnnxEngine
B=Path(__file__).resolve().parents[1]/'build/vocal_oss_20261029'
pcm=np.fromfile(B/'inputs/zuguo/full.f32',dtype='<f4')[round(47.09*16000):round(55.09*16000)]
results=[]
for i in range(2):
    engine=GameOnnxEngine(size='small',boundary_threshold=.3)
    ns,tr=engine.recognize(pcm);results.append(ns)
    assert all(n['start_ms']>=0 and n['duration_ms']>0 and n['start_ms']+n['duration_ms']<=8000 for n in ns)
    assert all(a['start_ms']+a['duration_ms']<=z['start_ms'] for a,z in zip(ns,ns[1:]))
silence,_=engine.recognize(np.zeros(16000*3,dtype=np.float32))
assert not silence,'trained model hallucinated notes on digital silence'
report={'separate_new_sessions_identical_output':results[0]==results[1],
        'output_1':results[0],'output_2':results[1],'digital_silence_events':len(silence),
        'clock_monotone_nonoverlap_bounds_pass':True,
        'human_listening_accepted':False,
        'note':'ONNX D3PM is stochastic; seed is engine initialization only. Cache hashes and exact outputs are retained.'}
(B/'real_inference_sanity.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if not k.startswith('output_')},indent=2))
