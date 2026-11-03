from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from recording_tonality import infer_collection
from context_pitch_consensus import refine_context
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029';NEW=R/'build/vocal_pitch_90_20261029'

for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/name/'full';ns=read_notes(d/'melodic_notes.csv')
    views=[np.load(d/f'context_{size}_{offset}.npz')['midi'] for size,offset in [(4000,0),(4000,2000),(8000,0)]]
    # A partial exploratory model cache must never change the inference policy.
    # The rejected lyric/pitch model is not a source for this candidate.
    out,audit=refine_context(ns,views,dict(np.load(PRE/name/'full/evidence.npz')),dict(np.load(d/'pesto.npz')),infer_collection(ns))
    write_notes(out,d/'context_consensus_notes.csv');(d/'context_consensus_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,audit['changes'],flush=True)
