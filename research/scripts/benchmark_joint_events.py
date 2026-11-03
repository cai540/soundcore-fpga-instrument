"""Benchmarks route files; the decoder gets only same-source acoustic arrays."""
from pathlib import Path
import argparse,json,numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from joint_event_pitch import decode_event_pitches
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',default='');args=p.parse_args()
    for name in ['zuguo','chilege','qiansixi','lantingxu']:
        if args.only and args.only not in name:continue
        d=B/'runs/medium_voice_beam1'/name/'full';ns=read_notes(d/'melody_context.csv')
        v=[]
        for width,offset in [(4000,0),(4000,2000),(8000,0)]:
            q=np.load(d/f'game_{width}_{offset}.npz');x=q['midi'].copy();x[~q['present']]=np.nan;v.append(x)
        e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/full/evidence.npz')
        pp=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/full/pesto.npz')
        cr=np.load(R/f'build/vocal_pitch_90_20261029/{name}/full/crepe.npz')
        bp=np.load(R/f'build/vocal_oss_20261029/basic/{name}/full/activations.npz')
        out,audit=decode_event_pitches(ns,v,e,pp,cr,bp)
        write_notes(out,d/'melody_joint.csv');(d/'joint_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,len(out),'changed',audit['changes'],flush=True)

if __name__=='__main__':main()
