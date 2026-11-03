from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from sustained_note_components import recover_components
from recording_tonality import infer_collection
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/name/'full';notes=read_notes(d/'context_register_notes.csv')
    views=[np.load(d/f'context_{w}_{o}.npz')['midi'] for w,o in [(4000,0),(4000,2000),(8000,0)]]
    basic=np.load(R/'build/vocal_oss_20261029/basic'/name/'full/activations.npz')
    out,audit=recover_components(notes,views,np.load(PRE/name/'full/evidence.npz'),np.load(d/'pesto.npz'),basic,infer_collection(notes))
    write_notes(out,d/'component_notes.csv')
    (d/'component_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,audit['split_regions'],audit['notes_added'],flush=True)
