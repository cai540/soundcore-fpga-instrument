"""Native-rate, single-singer baseline with content-addressed observations.

One singing transcription model supplies both boundaries and pitch. No
polyphonic instrument model, song identity, old MIDI or lyric database enters.
This remains an experimental desktop engine, not an accepted App release.
"""
from pathlib import Path
import hashlib,json,math,time
import numpy as np
from scipy.signal import resample_poly
from game_vocal_engine import GameOnnxEngine,core_stitch

def native_context_cuts(pcm,rate):
    length=round(len(pcm)*1000/rate);hop=max(1,round(rate*.02))
    energy=np.array([np.sqrt(np.mean(pcm[a:a+hop].astype(float)**2)) for a in range(0,len(pcm),hop)])
    quiet=energy<max(.001,float(np.quantile(energy,.9))*.06);cuts=[0]
    while length-cuts[-1]>22000:
        low=cuts[-1]+12000;high=min(length,cuts[-1]+21000);runs=[];start=None
        for i in range(low//20,high//20):
            if quiet[i] and start is None:start=i
            elif not quiet[i] and start is not None:
                if i-start>=9:runs.append((start,i))
                start=None
        if start is not None and high//20-start>=9:runs.append((start,high//20))
        cut=min(runs,key=lambda r:abs((r[0]+r[1])*10-(cuts[-1]+18000))) if runs else None
        cuts.append(round((cut[0]+cut[1])*10) if cut else cuts[-1]+18000)
    return cuts+[length]

class NativeVoiceEngine:
    def __init__(self,cache,size='medium',language='zh',steps=8):
        self.engine=GameOnnxEngine(size=size,steps=steps);self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.rate=self.engine.rate;self.steps=steps;self.language=language
        if language not in self.engine.config.get('languages',{}):raise ValueError('Unsupported language')

    def infer(self,pcm):
        e=self.engine;source_sha=hashlib.sha256(pcm.tobytes()).hexdigest()
        encoder_key=hashlib.sha256(json.dumps([source_sha,self.rate,e.weights['encoder.onnx']],sort_keys=True).encode()).hexdigest()
        directory=self.cache/encoder_key;directory.mkdir(exist_ok=True)
        dst=directory/'encoder.npz';hit=dst.exists()
        if hit:
            with np.load(dst) as q:xs=q['x_seg'];xe=q['x_est'];mask=q['mask']
        else:
            xs,xe,mask=e.sessions['encoder'].run(None,{'waveform':pcm[None,:],'duration':np.array([len(pcm)/self.rate],np.float32)})
            np.savez_compressed(dst,x_seg=xs,x_est=xe,mask=mask)
        params_sha=hashlib.sha256(json.dumps([self.steps,self.language,e.weights['segmenter.onnx'],e.weights['estimator.onnx'],
                                           e.weights['bd2dur.onnx'],'native-voice-raw-v1'],sort_keys=True).encode()).hexdigest()
        result_file=directory/f'{params_sha}.json'
        if result_file.exists():
            result=json.loads(result_file.read_text());result['encoder_cache_hit']=True;result['note_cache_hit']=True;return result
        known=np.zeros(mask.shape,bool);boundaries=known.copy()
        params={'x_seg':xs,'known_boundaries':known,'maskT':mask,'threshold':np.array(.2,np.float32),'radius':np.array(2,np.int64),
                'language':np.array([e.config['languages'][self.language]],np.int64)}
        for t in np.arange(self.steps,dtype=np.float32)/self.steps:
            params.update(prev_boundaries=boundaries,t=np.array([t],np.float32))
            boundaries=e.sessions['segmenter'].run(None,params)[0]
        ds,nmask=e.sessions['bd2dur'].run(None,{'boundaries':boundaries,'maskT':mask})
        presence,pitch=e.sessions['estimator'].run(None,{'x_est':xe,'boundaries':boundaries,'maskT':mask,'maskN':nmask,'threshold':np.array(.2,np.float32)})
        regions=[];cursor=0.;length_ms=round(len(pcm)*1000/self.rate)
        for duration,on,value,valid in zip(ds[0],presence[0],pitch[0],nmask[0]):
            if not valid:break
            a=round(cursor*1000);cursor+=float(duration);z=min(round(cursor*1000),length_ms)
            if z<=a:continue
            regions.append({'start_ms':a,'duration_ms':z-a,'midi':int(np.floor(value+.5)) if on else 0,
                            'continuous_midi':float(value),'confidence':0.})
        if abs(cursor*1000-length_ms)>11:raise RuntimeError('Model/source clock mismatch')
        result={'regions':regions,'source_sha256':source_sha,'encoder_cache_hit':hit,'note_cache_hit':False,
                'boundary_frames':np.flatnonzero(boundaries[0]).tolist()}
        result_file.write_text(json.dumps(result),encoding='utf8');return result

    def recognize(self,pcm,rate,progress=lambda *a:None):
        pcm=np.asarray(pcm,dtype=np.float32)
        if not 8000<=rate<=192000:raise ValueError('Unsupported sample rate')
        if pcm.ndim!=1 or not np.isfinite(pcm).all() or not 100<=len(pcm)*1000/rate<=600000:
            raise ValueError('Finite mono audio, 0.1 to 600 seconds, required')
        if rate!=self.rate:
            g=math.gcd(rate,self.rate);pcm=resample_poly(pcm,self.rate//g,rate//g).astype(np.float32)
        cuts=native_context_cuts(pcm,self.rate);events=[];traces=[];start=time.perf_counter()
        for i,(a,z) in enumerate(zip(cuts,cuts[1:])):
            begin=max(0,a-1200);end=min(cuts[-1],z+1200)
            part=pcm[round(begin*self.rate/1000):round(end*self.rate/1000)]
            result=self.infer(part);events=core_stitch(events,result['regions'],begin,a,z)
            traces.append({'core_start_ms':a,'core_end_ms':z,'context_start_ms':begin,'context_end_ms':end,**result})
            progress(i+1,len(cuts)-1)
        notes=[{k:n[k] for k in ['start_ms','duration_ms','midi','confidence']} for n in events if n['midi']>0]
        return notes,{'version':'native-single-singer-research-v9','source_ms':cuts[-1],'analysis_rate':self.rate,
                      'native_analysis_pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),'steps':self.steps,
                      'language':self.language,'weights_sha256':self.engine.weights,'chunks':traces,
                      'runtime_seconds':time.perf_counter()-start,'notes':len(notes),
                      'legacy_resampler_used':False,'polyphonic_model_used':False,'pitch_model_fusion_used':False,
                      'lyrics_or_old_score_used':False,'real_world_90_percent_verified':False}
