"""Independent, cached pitch observations. No score/lyric inputs."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029'
sys.path.insert(0,str(B/'extra'))
from benchmark_oss_vocals import inputs

def pesto_extract(model,pcm):
    import torch
    from game_vocal_engine import context_cuts
    T=(len(pcm)//16+9)//10;cuts=context_cuts(pcm)
    prediction=np.zeros(T,np.float32);confidence=np.zeros(T,np.float32);activations=np.zeros((T,384),np.float16)
    for idx,(a,z) in enumerate(zip(cuts,cuts[1:])):
        begin=max(0,a-1200);end=min(len(pcm)//16,z+1200)
        with torch.inference_mode():
            pitch,conf,vol,act=model(torch.from_numpy(pcm[begin*16:end*16]),sr=16000,convert_to_freq=False,return_activations=True)
        frames=np.arange((a+9)//10,min((z+9)//10,T));local=np.rint((frames*10-begin)/10).astype(int).clip(0,len(pitch)-1)
        prediction[frames]=pitch.cpu().numpy()[local];confidence[frames]=conf.cpu().numpy()[local]
        activations[frames]=act.cpu().numpy()[local]
        print('context',idx+1,'/',len(cuts)-1,flush=True)
    return {'midi':prediction,'confidence':confidence,'probabilities':activations}

def world_extract(pcm):
    import pyworld
    f0,ts=pyworld.dio(pcm.astype(np.float64),16000,f0_floor=50,f0_ceil=1600,frame_period=10)
    refined=pyworld.stonemask(pcm.astype(np.float64),f0,ts,16000)
    T=(len(pcm)//16+9)//10
    return {'f0':refined[:T].astype(np.float32)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['pesto','world','pyin'],required=True);p.add_argument('--only',default='');args=p.parse_args()
    model=None;results=[]
    for name,window,path,offset in inputs():
        key=name+'/'+window
        if args.only and args.only not in key:continue
        d=B/name/window;d.mkdir(parents=True,exist_ok=True)
        dst=d/(args.engine+'.npz');pcm=np.fromfile(path,dtype='<f4');digest=hashlib.sha256(pcm.tobytes()).hexdigest()
        if dst.exists():print('cached',args.engine,key,flush=True);continue
        print('start',args.engine,key,flush=True);t=time.perf_counter()
        if args.engine=='pesto':
            if model is None:
                import torch,pesto
                torch.set_num_threads(6);model=pesto.load_model('mir-1k_g7',step_size=10.,sampling_rate=16000)
            out=pesto_extract(model,pcm)
        elif args.engine=='world':out=world_extract(pcm)
        else:
            import librosa
            f0,voiced,prob=librosa.pyin(pcm,fmin=50,fmax=1600,sr=16000,frame_length=2048,hop_length=160,fill_na=0)
            T=(len(pcm)//16+9)//10;out={'f0':f0[:T].astype(np.float32),'confidence':prob[:T].astype(np.float32)}
        np.savez_compressed(dst,**out)
        info={'name':name,'window':window,'engine':args.engine,'pcm_sha256':digest,'runtime_seconds':time.perf_counter()-t,
              'frames':len(next(iter(out.values()))),'frame_ms':10,'input':str(path),'source_ms':len(pcm)//16,'source_offset_seconds':offset}
        (d/(args.engine+'.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8');results.append(info)
        print('done',args.engine,key,round(info['runtime_seconds'],2),flush=True)
    (B/(args.engine+'_runs.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
