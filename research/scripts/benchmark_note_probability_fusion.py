from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from recording_tonality import infer_collection
from note_probability_fusion import fuse_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029';NEW=R/'build/vocal_pitch_90_20261029'

for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/name/'full';ns=read_notes(d/'context_consensus_notes.csv')
    views=[np.load(d/f'context_{size}_{offset}.npz')['midi'] for size,offset in [(4000,0),(4000,2000),(8000,0)]]
    basic=np.load(R/'build/vocal_oss_20261029/basic'/name/'full/activations.npz')
    out,audit=fuse_notes(ns,views,basic,dict(np.load(NEW/name/'full/crepe.npz')),dict(np.load(d/'pesto.npz')),infer_collection(ns))
    write_notes(out,d/'probability_fusion_notes.csv');(d/'probability_fusion_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,audit['changes'],flush=True)
