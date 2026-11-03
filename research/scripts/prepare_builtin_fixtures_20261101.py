"""Evaluation-only fixtures; never packaged in the application."""
from pathlib import Path
import json,math,sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'build/builtin_recognition_20261101';out.mkdir(exist_ok=True)
cases=json.loads((ROOT/'build/vocal_40s_phrase_20261030/inputs.json').read_text(encoding='utf8'))['cases']
for c in cases:
    rate,pcm=wavfile.read(ROOT/c['clip']);pcm=pcm.astype(np.float32)
    if pcm.ndim>1:pcm=pcm.mean(axis=1)
    if float(abs(pcm).max())>2:raise ValueError('Expected floating-point research source WAV')
    d=math.gcd(rate,16000);pcm=resample_poly(pcm,16000//d,rate//d)[:640000].astype('<f4')
    pcm.tofile(out/(c['id']+'.f32'))
with np.load(ROOT/'build/fpga_omr_20261031/model/validation_vectors.npz',allow_pickle=False)as v:
    rows=[{'hex':np.packbits(x.astype(np.uint8),bitorder='little').tobytes().hex(),'logits':y.tolist()}for x,y in zip(v['x'],v['logits'])]
(out/'symbol_vectors.json').write_text(json.dumps(rows),encoding='utf8')
(out/'source_cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf8')
print('Prepared3real40sPCMfilesand183symbolvectors')
