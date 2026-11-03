"""Actual new-model inference on the same PCM as earlier candidates.

Names below route evaluation files only. The engine receives waveform and
input kind (voice), never old notes, lyrics, key signatures or song identity.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from muscriptor_public_engine import MuscriptorEngine,B
from monophonic_event_path import select_melody
from transcribe_vocal_oss import write_notes
from benchmark_oss_vocals import inputs


def main():
    p=argparse.ArgumentParser();p.add_argument('--size',default='medium',choices=['small','medium','large']);p.add_argument('--all-windows',action='store_true')
    p.add_argument('--only',default='');p.add_argument('--beam-size',type=int,default=1)
    p.add_argument('--precision',choices=['float16','float32'],default='float32');args=p.parse_args()
    model=None;results=[]
    for name,window,path,offset in inputs():
        if not args.all_windows and window!='full':continue
        if args.only and args.only not in name+'/'+window:continue
        pcm=np.fromfile(path,dtype='<f4');digest=hashlib.sha256(pcm.tobytes()).hexdigest()
        tag=f'{args.size}_voice_beam{args.beam_size}'+('_fp32' if args.precision=='float32' else '')
        d=B/'runs'/tag/name/window;d.mkdir(parents=True,exist_ok=True)
        cached=False
        if (d/'result.json').exists():
            info=json.loads((d/'result.json').read_text(encoding='utf8'))
            cached=(info['source_pcm_sha256']==digest and info['size']==args.size and info['beam_size']==args.beam_size)
        if cached:raw=json.loads((d/'raw_notes.json').read_text(encoding='utf8'));print('cached model',name,window,flush=True)
        else:
            if model is None:model=MuscriptorEngine(args.size,args.precision)
            print('infer',name,window,len(pcm)/16000,flush=True)
            raw,events,midi,info=model.recognize(pcm,('voice',),lambda i,n:print(name,window,i,'/',n,flush=True),args.beam_size)
            (d/'raw_notes.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf8')
            (d/'raw_events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf8')
            (d/'raw.mid').write_bytes(midi)
            (d/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
        notes,audit=select_melody(raw);write_notes(notes,d/'melody.csv')
        (d/'selection.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
        row={'name':name,'window':window,'raw_notes':len(raw),'main_notes':len(notes),'source_offset_seconds':offset,
             'new_model_cache_hit':cached,'runtime_seconds':info['runtime_seconds'],'source_pcm_sha256':digest}
        results.append(row);print('saved',row,flush=True)
    (B/f'{tag}_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
