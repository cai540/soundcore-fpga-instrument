from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from melodic_pitch_refiner import refine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def main():
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        d=B/name/'full';old=read_notes(PRE/name/'full/notes.csv')
        evidence=np.load(PRE/name/'full/evidence.npz');pesto=np.load(d/'pesto.npz');melodia=np.load(d/'melodia.npz')
        info=json.loads((d/'result.json').read_text());pcm=np.fromfile(info['input_file'],dtype='<f4')
        new,audit=refine(old,pcm,evidence['rmvpe'],pesto['midi'],pesto['confidence'],melodia['f0'])
        assert [(n['start_ms'],n['duration_ms']) for n in old]==[(n['start_ms'],n['duration_ms']) for n in new]
        write_notes(new,d/'melodic_notes.csv');(d/'melodic_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,'changes',audit['changes'],'prior',audit['prior'],flush=True)

if __name__=='__main__':main()
