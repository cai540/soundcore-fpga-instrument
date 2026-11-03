"""Optional third event model, without introducing any new onset."""
from pathlib import Path
import argparse,json,numpy as np
from transcription_event_consensus import consensus_events
from transcribe_vocal_oss import write_notes
from evaluate_oss_vocals import read_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
p=argparse.ArgumentParser();p.add_argument('--lattice',action='store_true');args=p.parse_args()
for name in ['zuguo','chilege','qiansixi','lantingxu']:
    d=B/'runs/medium_voice_beam1'/name/'full'
    schedule=read_notes(d/'melody_lattice.csv') if args.lattice else None
    raw=json.loads((d/'raw_notes.json').read_text());alt=json.loads((B/'runs/large_voice_beam1'/name/'full/raw_notes.json').read_text())
    small=json.loads((B/'runs/small_voice_beam1'/name/'full/raw_notes.json').read_text())
    views=[]
    for w,o in [(4000,0),(4000,2000),(8000,0)]:
        dst=d/f'{"lattice_" if args.lattice else ""}game_{w}_{o}.npz'
        if not dst.exists():break
        q=np.load(dst);v=q['midi'].copy();v[~q['present']]=np.nan;views.append(v)
    if len(views)!=3:continue
    if schedule is not None and len(views[0])!=len(schedule):continue
    e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/evidence.npz')
    p=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/full/pesto.npz')
    c=np.load(R/f'build/vocal_pitch_90_20261029/{name}/full/crepe.npz')
    b=np.load(R/f'build/vocal_oss_20261029/basic/{name}/full/activations.npz')
    notes,audit=consensus_events(raw,alt,views,e,p,c,b,note_schedule=schedule,confirmation=small)
    tag='lattice_confirmed' if args.lattice else 'confirmed'
    write_notes(notes,d/f'melody_{tag}.csv');(d/f'{tag}_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(name,len(notes),flush=True)
