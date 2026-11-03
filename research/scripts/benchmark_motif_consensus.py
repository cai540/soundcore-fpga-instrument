from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from recording_motif_consensus import refine_repeats
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';NEW=R/'build/vocal_pitch_90_20261029'
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/name/'full';notes=read_notes(d/'context_consensus_notes.csv')
    basic=np.load(R/'build/vocal_oss_20261029/basic'/name/'full/activations.npz')
    out,audit=refine_repeats(notes,basic,dict(np.load(NEW/name/'full/crepe.npz')))
    write_notes(out,d/'motif_notes.csv')
    (d/'motif_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,audit['changes'],'matches',len(audit['paths']),flush=True)
