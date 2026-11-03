"""Recompute acoustic estimates on the interval-lattice schedule itself."""
from pathlib import Path
import argparse,hashlib,json,numpy as np
from benchmark_oss_vocals import inputs
from estimate_pitch_contexts import ContextualGamePitchEstimator
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_notes
from transcription_event_consensus import consensus_events
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',default='');p.add_argument('--all-windows',action='store_true');args=p.parse_args();engine=None
    for name,window,path,_ in inputs():
        if (not args.all_windows and window!='full') or (args.only and args.only not in name):continue
        d=B/'runs/medium_voice_beam1'/name/window;file=d/'melody_lattice.csv'
        if not file.exists():continue
        ns=read_notes(file);pcm=np.fromfile(path,dtype='<f4');source=hashlib.sha256(pcm.tobytes()).hexdigest()
        signature=hashlib.sha256(json.dumps([(n['start_ms'],n['duration_ms']) for n in ns]).encode()).hexdigest();views=[]
        for w,o in [(4000,0),(4000,2000),(8000,0)]:
            dst=d/f'lattice_game_{w}_{o}.npz';valid=False
            if dst.exists():
                q=np.load(dst);valid=str(q['source_sha256'])==source and str(q['boundaries_sha256'])==signature
            if not valid:
                if engine is None:engine=ContextualGamePitchEstimator()
                print('context',name,w,o,flush=True);q=engine.predict(pcm,ns,w,o)
                np.savez_compressed(dst,**q,source_sha256=source,boundaries_sha256=signature)
            q=np.load(dst);v=q['midi'].copy();v[~q['present']]=np.nan;views.append(v)
        e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/{window}/evidence.npz')
        pp=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/{window}/pesto.npz')
        cr=np.load(R/f'build/vocal_pitch_90_20261029/{name}/{window}/crepe.npz')
        bp=np.load(R/f'build/vocal_oss_20261029/basic/{name}/{window}/activations.npz')
        raw=json.loads((d/'raw_notes.json').read_text());alt=json.loads((B/'runs/large_voice_beam1'/name/window/'raw_notes.json').read_text())
        notes,audit=consensus_events(raw,alt,views,e,pp,cr,bp,note_schedule=ns)
        write_notes(notes,d/'melody_lattice_context.csv');(d/'lattice_context_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print('saved',name,len(notes),flush=True)

if __name__=='__main__':main()
