"""Estimate fixed note pitches in several local acoustic contexts.

Only note times and waveform enter GAME. Full notes are never clipped at
analysis boundaries, and the original note schedule is not modified.
"""
from pathlib import Path
import argparse,json,time,hashlib,math
import numpy as np
from scipy.signal import resample_poly
from game_vocal_engine import GameOnnxEngine
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import decode_audio
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';PRE=R/'build/vocal_syllable_main_20261029'

class ContextualGamePitchEstimator:
    def __init__(self,sample_rate=16000,cache=None):
        if not 8000<=sample_rate<=192000:raise ValueError('Unsupported sample rate')
        self.engine=GameOnnxEngine(size='medium');self.sample_rate=sample_rate
        self.cache=Path(cache) if cache is not None else None
        if self.cache is not None:self.cache.mkdir(parents=True,exist_ok=True)

    def infer(self,pcm,notes,begin_ms,end_ms):
        begin_ms=int(begin_ms);end_ms=int(end_ms)
        engine=self.engine;rate=getattr(self,'sample_rate',16000)
        piece=pcm[round(begin_ms*rate/1000):round(end_ms*rate/1000)]
        relevant=[n for n in notes if n['start_ms']<end_ms and n['start_ms']+n['duration_ms']>begin_ms]
        signature=hashlib.sha256(json.dumps([
            'fixed-native-context-v2',rate,begin_ms,end_ms,
            hashlib.sha256(piece.tobytes()).hexdigest(),engine.weights,
            [(n['start_ms'],n['duration_ms']) for n in relevant]],sort_keys=True).encode()).hexdigest()
        destination=self.cache/(signature+'.json') if getattr(self,'cache',None) is not None else None
        if destination is not None and destination.exists():return json.loads(destination.read_text())
        if rate==engine.rate:waveform=piece[None,:]
        else:
            divisor=math.gcd(engine.rate,rate)
            waveform=resample_poly(piece,engine.rate//divisor,rate//divisor).astype(np.float32)[None,:]
        _,xe,mask=engine.sessions['encoder'].run(None,{'waveform':waveform,'duration':np.array([len(piece)/rate],np.float32)})
        boundaries=np.zeros(mask.shape,bool);T=int(mask.sum())
        for n in notes:
            for t in [n['start_ms'],n['start_ms']+n['duration_ms']]:
                k=round((t-begin_ms)/10)
                if 0<k<T-1:boundaries[0,k]=True
        dur,nmask=engine.sessions['bd2dur'].run(None,{'boundaries':boundaries,'maskT':mask})
        presence,pitch=engine.sessions['estimator'].run(None,{'x_est':xe,'boundaries':boundaries,'maskT':mask,'maskN':nmask,
                                                           'threshold':np.array(.2,np.float32)})
        cursor=begin_ms;regions=[]
        for d,on,p,valid in zip(dur[0],presence[0],pitch[0],nmask[0]):
            if not valid:break
            end=cursor+round(float(d)*1000)
            regions.append((cursor,end,float(p),bool(on)));cursor=end
        if destination is not None:destination.write_text(json.dumps(regions),encoding='utf8')
        return regions

    def predict(self,pcm,notes,core_ms=4000,offset_ms=0,progress=lambda *a:None):
        length=round(len(pcm)*1000/getattr(self,'sample_rate',16000));result=np.zeros(len(notes),np.float32);present=np.zeros(len(notes),bool)
        if not notes:return {'midi':result,'present':present}
        centers=np.array([n['start_ms']+n['duration_ms']/2 for n in notes]);bins=np.floor((centers-offset_ms)/core_ms).astype(int)
        unique=np.unique(bins)
        for i,b in enumerate(unique):
            selected=np.flatnonzero(bins==b)
            a=max(0,b*core_ms+offset_ms-2000);z=min(length,(b+1)*core_ms+offset_ms+2000)
            # Preserve the entirety of every target note, plus acoustic edges.
            a=max(0,min(a,min(notes[j]['start_ms'] for j in selected)-200))
            z=min(length,max(z,max(notes[j]['start_ms']+notes[j]['duration_ms'] for j in selected)+200))
            regions=self.infer(pcm,notes,a,z)
            for j in selected:
                n=notes[j];overlaps=[(min(e,n['start_ms']+n['duration_ms'])-max(s,n['start_ms']),p,on) for s,e,p,on in regions]
                duration,p,on=max(overlaps,key=lambda q:q[0])
                if duration>=n['duration_ms']-20:result[j]=p;present[j]=on
            progress(i+1,len(unique))
        return {'midi':result,'present':present}

def main():
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');args=p.parse_args();model=ContextualGamePitchEstimator()
    if args.smoke:
        ns=read_notes(PRE/'zuguo/full/notes.csv');a=47090;z=55090;ns=[{**n,'start_ms':n['start_ms']-a} for n in ns if n['start_ms']>=a and n['start_ms']+n['duration_ms']<=z]
        original=np.fromfile(R/'build/vocal_oss_20261029/inputs/zuguo/full.f32',dtype='<f4')
        native=decode_audio(R/'songs/source/wodezuguo_vocals_20261026.mp3')
        for tag,pcm in [('archive',original),('native',native)]:
            regions=model.infer(pcm[a*16:z*16],ns,0,z-a)
            print(tag,regions,flush=True)
        return
    for name,window,path,_ in inputs():
        d=B/name/window;notes=read_notes(PRE/name/window/'notes.csv');pcm=np.fromfile(path,dtype='<f4')
        for core,offset in [(4000,0),(4000,2000),(8000,0)]:
            dst=d/f'context_{core}_{offset}.npz'
            if dst.exists():print('cached',dst,flush=True);continue
            print('context view',name,window,core,offset,flush=True)
            data=model.predict(pcm,notes,core,offset,lambda i,n:print(i,'/',n,flush=True))
            np.savez_compressed(dst,**data)

if __name__=='__main__':main()
