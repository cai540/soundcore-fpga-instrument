"""Diagnostic paired inputs only. No transcript or target notes enter model."""
from pathlib import Path
import json,subprocess
import numpy as np
from vocalparse_pitch_engine import VocalParseEngine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_90_20261029'
engine=VocalParseEngine();rows=[]
for kind,start in [('original',88.07),('vocals',88.07),('original',176.95),('vocals',176.95)]:
    f=R/f'songs/source/wodezuguo_{kind}_20261026.mp3'
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(f),'-t','6','-ac','1','-ar','16000','-f','f32le','-'])
    result=engine.infer(np.frombuffer(raw,dtype='<f4').copy(),max_tokens=256)
    rows.append({'input_kind':kind,'start_seconds':start,**result})
    (B/'paired_input_diagnostic.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print(kind,start,result['token_limit_reached'],result['raw_text'][:150],result['parsed'],flush=True)
