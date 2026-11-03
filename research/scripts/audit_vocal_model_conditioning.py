"""Ablate an assumed voice constraint and greedy decoding, without fusion."""
from pathlib import Path
import json,numpy as np
from muscriptor_public_engine import MuscriptorEngine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v9_20261029'
engine=MuscriptorEngine('medium','float32')
for name in ['zuguo','qiansixi']:
    x=np.fromfile(B/'input_ab'/name/'native/input.f32',dtype='<f4')
    for tag,instruments,beam in [('automatic_greedy',None,1),('voice_beam4',('voice',),4)]:
        out=B/'conditioning'/name/tag;out.mkdir(parents=True,exist_ok=True)
        notes,events,midi,info=engine.recognize(x,instruments,beam_size=beam)
        (out/'raw_notes.json').write_text(json.dumps(notes,indent=2),encoding='utf8')
        (out/'raw.mid').write_bytes(midi);(out/'result.json').write_text(json.dumps(info,indent=2),encoding='utf8')
        counts={k:sum(n['instrument']==k for n in notes) for k in {n['instrument'] for n in notes}}
        print(name,tag,'notes',len(notes),'instruments',counts,flush=True)
