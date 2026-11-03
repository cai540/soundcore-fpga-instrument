from pathlib import Path
import json
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from register_sequence_decoder import decode_register
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

def main():
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        d=B/name/'full';notes=read_notes(d/'melodic_notes.csv')
        ns,audit=decode_register(notes,dict(np.load(PRE/name/'full/evidence.npz')),dict(np.load(d/'pesto.npz')),dict(np.load(d/'melodia.npz')))
        write_notes(ns,d/'sequence_notes.csv');(d/'sequence_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,audit['changes'],flush=True)

if __name__=='__main__':main()
