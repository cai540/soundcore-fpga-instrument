from pathlib import Path
import argparse,json,numpy as np
from periodic_vowel_events import collapse_periodic_vowels
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
p=argparse.ArgumentParser();p.add_argument('--input',default='consensus_raw');args=p.parse_args()
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/'runs/medium_voice_beam1'/name/'full';notes=read_notes(d/f'melody_{args.input}.csv')
    e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/evidence.npz')
    p=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/full/pesto.npz')
    out,audit=collapse_periodic_vowels(notes,e,p)
    write_notes(out,d/f'melody_{args.input}_periodic.csv');(d/f'{args.input}_periodic_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,len(notes),'->',len(out),'removed',audit['events_removed'],flush=True)
