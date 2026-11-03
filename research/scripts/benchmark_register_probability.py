from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from sequence_register_probability import decode_register
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';NEW=R/'build/vocal_pitch_90_20261029'
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/name/'full';notes=read_notes(d/'context_consensus_notes.csv')
    basic=np.load(R/'build/vocal_oss_20261029/basic'/name/'full/activations.npz')
    out,audit=decode_register(notes,basic,dict(np.load(NEW/name/'full/crepe.npz')),dict(np.load(d/'pesto.npz')))
    write_notes(out,d/'register_probability_notes.csv')
    (d/'register_probability_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,audit['changes'],flush=True)
