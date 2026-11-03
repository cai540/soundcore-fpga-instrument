"""Ask GAME's trained pitch estimator about the complete acoustic syllable.

Boundaries come from the generic decoder, not lyrics/reference scores. This
avoids choosing the main syllable pitch by averaging old fragmented notes.
"""
from pathlib import Path
import json
import numpy as np
from scipy.signal import resample_poly
from game_vocal_engine import GameOnnxEngine,context_cuts
from benchmark_oss_vocals import inputs
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029'

class SyllablePitchEstimator:
    def __init__(self):self.engine=GameOnnxEngine(size='medium')

    def estimate(self,pcm,syllables,progress=lambda *args:None):
        engine=self.engine;length=len(pcm)//16;cuts=context_cuts(pcm)
        observations=[[] for _ in syllables]
        for i,(a,z) in enumerate(zip(cuts,cuts[1:])):
            begin=max(0,a-1200);end=min(length,z+1200);piece=pcm[begin*16:end*16]
            wav=resample_poly(piece,engine.rate//100,160).astype(np.float32)[None,:]
            xs,xe,mask=engine.sessions['encoder'].run(None,{'waveform':wav,'duration':np.array([len(piece)/16000],np.float32)})
            boundaries=np.zeros(mask.shape,bool)
            for s in syllables:
                for t in [s['start_ms'],s['end_ms']]:
                    k=round((t-begin)/10)
                    if 0<k<int(mask.sum())-1:boundaries[0,k]=True
            durations,nmask=engine.sessions['bd2dur'].run(None,{'boundaries':boundaries,'maskT':mask})
            presence,pitches=engine.sessions['estimator'].run(None,{'x_est':xe,'boundaries':boundaries,'maskT':mask,'maskN':nmask,
                                                                  'threshold':np.array(.2,np.float32)})
            cursor=begin
            for dur,present,pitch,valid in zip(durations[0],presence[0],pitches[0],nmask[0]):
                if not valid:break
                s=cursor;e=cursor+round(float(dur)*1000);cursor=e
                if not present:continue
                for j,unit in enumerate(syllables):
                    overlap=min(e,unit['end_ms'],z)-max(s,unit['start_ms'],a)
                    if overlap>0:observations[j].append((float(pitch),overlap))
            progress(i+1,len(cuts)-1)
        result=[]
        for unit,obs in zip(syllables,observations):
            q=dict(unit)
            q['estimator_present']=bool(obs)
            if obs:
                # Core-duration weighted pitch; exact seam-only duplicates do
                # not get an extra vote or stretch the source time.
                continuous=float(np.average([o[0] for o in obs],weights=[o[1] for o in obs]))
                q['continuous_midi']=continuous;q['midi']=int(np.floor(continuous+.5))
            else:q['continuous_midi']=float(unit['main_midi']);q['midi']=unit['main_midi']
            result.append(q)
        return result

def main():
    estimator=SyllablePitchEstimator()
    for name,window,path,_ in inputs():
        d=B/name/window
        if not (d/'syllable_audit.json').exists():continue
        units=json.loads((d/'syllable_audit.json').read_text())['syllables']
        print('reestimate',name,window,flush=True)
        out=estimator.estimate(np.fromfile(path,dtype='<f4'),units,lambda i,n:print(i,'/',n,flush=True))
        (d/'syllable_pitch.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
        print('saved',name,window,flush=True)

if __name__=='__main__':main()
