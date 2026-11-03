"""Re-estimate pitch on the NEW model's onsets, not the v6 note schedule."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from estimate_pitch_contexts import ContextualGamePitchEstimator
from monophonic_event_path import select_melody
from transcribe_vocal_oss import write_notes
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'


def main():
    p=argparse.ArgumentParser();p.add_argument('--size',default='medium');p.add_argument('--only',default='');args=p.parse_args()
    engine=None
    for name,window,path,offset in inputs():
        if window!='full' or (args.only and args.only not in name):continue
        d=B/'runs'/f'{args.size}_voice_beam1'/name/window
        if not (d/'raw_notes.json').exists():continue
        raw=json.loads((d/'raw_notes.json').read_text());notes,_=select_melody(raw);pcm=np.fromfile(path,dtype='<f4')
        views=[];signature=hashlib.sha256(json.dumps([(n['start_ms'],n['duration_ms']) for n in notes]).encode()).hexdigest()
        for width,off in [(4000,0),(4000,2000),(8000,0)]:
            dst=d/f'game_{width}_{off}.npz';valid=False
            if dst.exists():
                data=np.load(dst);valid=str(data['boundary_sha256'])==signature
            if not valid:
                if engine is None:engine=ContextualGamePitchEstimator()
                print('pitch context',args.size,name,width,off,flush=True)
                data=engine.predict(pcm,notes,width,off)
                np.savez_compressed(dst,**data,boundary_sha256=signature)
            data=np.load(dst);view=data['midi'].copy();view[~data['present']]=np.nan;views.append(view)
        result,audit=select_melody(raw,np.asarray(views).T)
        write_notes(result,d/'melody_context.csv')
        (d/'selection_context.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        print('saved',name,len(result),flush=True)

if __name__=='__main__':main()
