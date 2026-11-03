"""Check actual RTL-rendered audio, including tail energy and overload."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1]/'build/fx_review'
result={}
for mask in range(8):
    y=np.array([int(s,16) for s in (P/f'after_{mask}.hex').read_text().splitlines()],dtype=np.int32)
    y[y>=32768]-=65536
    assert len(y)==240000
    assert np.max(np.abs(y))<=10001,(mask,'gain overflow')
    assert abs(float(y.mean()))<8,(mask,'DC offset')
    assert np.max(np.abs(y[:24000]))==0,(mask,'startup stale RAM')
    if mask==0:assert np.max(np.abs(y[144000:]))==0
    if mask&1:assert np.max(np.abs(y[38390:38420]))>500,(mask,'missing 300 ms echo')
    if mask&2:assert np.max(np.abs(y[24600:24950]))>300,(mask,'missing delayed chorus')
    if mask&4:assert np.max(np.abs(y[25410:25460]))>20,(mask,'missing room reflection')
    sf.write(P/f'after_{mask}.wav',y/32768,48000)
    result[str(mask)]={'peak':int(np.max(np.abs(y))), 'mean':float(y.mean()),
                      'active_rms':float(np.sqrt(np.mean(y[72000:139200].astype(float)**2))),
                      'tail_peak':int(np.max(np.abs(y[144000:]))),'clipped':int(np.sum(np.abs(y)>=32767))}
(P/'product_metrics.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
