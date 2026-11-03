"""CPU ONNX adapter for OpenVPI GAME 1.0.3, following official ONNX.md.

No lyric, known score, musical key, filename or file identity is an input.
The official released waveform encoder includes its own spectrogram front end.
"""
from pathlib import Path
import json,time,hashlib
import numpy as np
from scipy.signal import resample_poly

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/vocal_oss_20261029'

def context_cuts(pcm):
    length=len(pcm)//16
    energy=np.array([np.sqrt(np.mean(pcm[i:i+320].astype(float)**2)) for i in range(0,len(pcm),320)])
    quiet=energy<max(.001,float(np.quantile(energy,.9))*.06)
    cuts=[0]
    while length-cuts[-1]>22000:
        low=cuts[-1]+12000;high=min(length,cuts[-1]+21000)
        runs=[];a=None
        for k in range(low//20,high//20):
            if quiet[k] and a is None:a=k
            elif not quiet[k] and a is not None:
                if k-a>=9:runs.append((a,k))
                a=None
        if a is not None and high//20-a>=9:runs.append((a,high//20))
        cut=min(runs,key=lambda x:abs((x[0]+x[1])*10-(cuts[-1]+18000))) if runs else None
        cuts.append(round((cut[0]+cut[1])*10) if cut else cuts[-1]+18000)
    return cuts+[length]

def core_stitch(all_events,raw,begin,a,z):
    core=[]
    for n in raw:
        s=n['start_ms']+begin;e=s+n['duration_ms']
        if min(e,z)<=max(s,a):continue
        core.append({**n,'start_ms':max(s,a),'duration_ms':min(e,z)-max(s,a),
                     'left_context_cut':s<a-80,'right_context_cut':e>z+80})
    if all_events and core:
        prev=all_events[-1];new=core[0]
        if (prev.get('right_context_cut') and new.get('left_context_cut') and prev['midi']==new['midi']
                and prev['start_ms']+prev['duration_ms']==new['start_ms']):
            prev['duration_ms']+=new['duration_ms'];prev['right_context_cut']=new['right_context_cut'];core=core[1:]
    return all_events+core

class GameOnnxEngine:
    def __init__(self,size='medium',threads=6,steps=8,boundary_threshold=.2,model_directory=None):
        import onnxruntime as ort
        assert size in ('small','medium') and steps>0
        self.size=size;self.steps=steps;self.boundary_threshold=boundary_threshold
        directory=Path(model_directory) if model_directory is not None else BASE/'game_models'/size
        configs=list(directory.rglob('config.json'))
        if len(configs)!=1:raise ValueError('Provide one unpacked GAME model directory with exactly one config.json')
        self.directory=configs[0].parent
        self.config=json.loads((self.directory/'config.json').read_text(encoding='utf8'))
        self.rate=self.config['samplerate'];self.dt=self.config['timestep']
        ort.set_seed(0)
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        self.sessions={name:ort.InferenceSession(str(self.directory/(name+'.onnx')),sess_options=options,providers=['CPUExecutionProvider'])
                       for name in ('encoder','segmenter','estimator','bd2dur')}
        self.weights={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.glob('*') if p.is_file()}

    def infer_chunk(self,pcm16):
        assert pcm16.ndim==1 and pcm16.dtype==np.float32 and np.isfinite(pcm16).all()
        # 16k PCM is held fixed across methods; original singing pitch is retained.
        wav=resample_poly(pcm16,self.rate//100,16000//100).astype(np.float32)[None,:]
        duration=np.array([len(pcm16)/16000],np.float32)
        x_seg,x_est,mask=self.sessions['encoder'].run(None,{'waveform':wav,'duration':duration})
        known=np.zeros(mask.shape,dtype=bool);boundaries=known.copy()
        params={'x_seg':x_seg,'known_boundaries':known,'maskT':mask,'threshold':np.array(self.boundary_threshold,np.float32),'radius':np.array(2,np.int64)}
        # Language is a single global setting, not a supplied transcript.
        if self.config.get('languages'):
            params['language']=np.array([self.config['languages'].get('zh',0)],np.int64)
        schedule=np.arange(self.steps,dtype=np.float32)/self.steps if self.config['loop'] else [None]
        for ti in schedule:
            if ti is not None:params.update(prev_boundaries=boundaries,t=np.array([ti],np.float32))
            boundaries=self.sessions['segmenter'].run(None,params)[0]
        durations,n_mask=self.sessions['bd2dur'].run(None,{'boundaries':boundaries,'maskT':mask})
        presence,scores=self.sessions['estimator'].run(None,{'x_est':x_est,'boundaries':boundaries,'maskT':mask,'maskN':n_mask,'threshold':np.array(.2,np.float32)})
        ns=[];cursor=0
        for dur,present,pitch,valid in zip(durations[0],presence[0],scores[0],n_mask[0]):
            if not valid:break
            start=round(cursor*1000);cursor+=float(dur);end=min(round(cursor*1000),round(duration[0]*1000))
            if end<=start:continue
            ns.append({'start_ms':start,'duration_ms':end-start,'midi':int(np.floor(pitch+.5)) if present else 0,
                       'continuous_midi':float(pitch),'confidence':0.0})
        assert abs(cursor-len(pcm16)/16000)<=self.dt+.002,(cursor,len(pcm16)/16000)
        return ns,{'boundary_frames':np.flatnonzero(boundaries[0]).tolist(),
                   'regions':ns,'model_frames':int(mask.sum()),'time_step':self.dt}

    def recognize(self,pcm16,progress=lambda *a:None):
        assert pcm16.dtype==np.float32 and len(pcm16)>=1600 and np.isfinite(pcm16).all()
        length=len(pcm16)//16;cuts=context_cuts(pcm16);events=[];traces=[];start=time.perf_counter()
        for idx,(a,z) in enumerate(zip(cuts,cuts[1:])):
            begin=max(0,a-1200);end=min(length,z+1200)
            raw,tr=self.infer_chunk(pcm16[begin*16:end*16])
            events=core_stitch(events,raw,begin,a,z)
            traces.append({**tr,'begin_ms':begin,'core_start_ms':a,'core_end_ms':z,'context_end_ms':end})
            progress(idx+1,len(cuts)-1)
        notes=[{k:n[k] for k in ('start_ms','duration_ms','midi','confidence')} for n in events if n['midi']>0]
        return notes,{'chunks':traces,'runtime_seconds':time.perf_counter()-start,'source_ms':length,'sample_rate':16000,
                      'weights_sha256':self.weights,'size':self.size,'steps':self.steps,'boundary_threshold':self.boundary_threshold,'presence_threshold':.2,
                      'seed':0,'language':'zh','explicit_rest_events':sum(q['midi']==0 for q in events),
                      'confidence_note':'presence returned as a thresholded boolean; confidence 0 means unavailable, not measured probability',
                      'software':'OpenVPI GAME 1.0.3 official ONNX; source-clock context adapter; no known boundaries'}
