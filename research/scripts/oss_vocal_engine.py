"""Song-independent research adapter to the official ROSVOT/RMVPE networks.

No reference notes, lyrics, file identity, target key or song clocks are inputs.
The implementation is kept outside Android until full-recording comparison.
Upstream: https://github.com/RickyL-2000/ROSVOT (MIT).
"""
from pathlib import Path
import sys,math,time,json,hashlib
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/vocal_oss_20261029'
sys.path.insert(0,str(BASE/'ROSVOT'))
import torch,yaml
from scipy.signal import resample_poly
from modules.rosvot.rosvot import MidiExtractor,WordbdExtractor
from modules.pe.rmvpe import RMVPE
from utils.commons.ckpt_utils import load_ckpt
from utils.commons.hparams import hparams as global_hparams
from utils.audio.mel import MelNet
from utils.audio.pitch_utils import norm_interp_f0,denorm_f0,f0_to_coarse,boundary2Interval

class RosvotEngine:
    def __init__(self,threads=6,profile='cli'):
        torch.set_num_threads(threads)
        self.hop=128;self.sr=24000;self.upstream=BASE/'ROSVOT'
        self.hp=yaml.safe_load((self.upstream/'checkpoints/rosvot/config.yaml').read_text(encoding='utf8'))
        self.wp=yaml.safe_load((self.upstream/'checkpoints/rwbd/config.yaml').read_text(encoding='utf8'))
        assert profile in ('cli','checkpoint')
        self.profile=profile
        # Two documented upstream defaults; one global profile for all audio.
        if profile=='cli':
            self.hp['note_bd_threshold']=.85;self.wp['word_bd_threshold']=.5
        global_hparams.clear();global_hparams.update(self.hp)
        self.model=MidiExtractor(self.hp).eval()
        load_ckpt(self.model,str(self.upstream/'checkpoints/rosvot/model.pt'),verbose=False)
        self.word=WordbdExtractor(self.wp).eval()
        load_ckpt(self.word,str(self.upstream/'checkpoints/rwbd/model.pt'),verbose=False)
        self.pitch=RMVPE(str(self.upstream/'checkpoints/rmvpe/model.pt'),device='cpu')
        self.mel=MelNet(self.hp);self.mel.to('cpu')
        self.weights={str(p.relative_to(self.upstream)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (self.upstream/'checkpoints').rglob('*') if p.is_file()}

    @torch.inference_mode()
    def infer_chunk(self,pcm16):
        """Return upstream event intervals including its explicit rest class 0."""
        assert pcm16.ndim==1 and np.isfinite(pcm16).all() and len(pcm16)>=1600
        wav=resample_poly(pcm16,3,2).astype(np.float32)
        real_frames=math.ceil(len(wav)/self.hop)
        frames=math.ceil(real_frames/16)*16
        # The upstream batch path applies min_gap=6 on the 10ms F0 grid.
        f0=self.pitch.infer_from_audio(pcm16,sample_rate=16000)
        f0=self.pitch.postprocess(f0,self.hp['f0_min'],self.hp['f0_max'],min_gap=6)
        from utils.audio.pitch_utils import resample_align_curve
        uv=f0==0
        aligned=resample_align_curve(f0,.01,self.hop/self.sr,real_frames)
        uv_aligned=resample_align_curve(uv.astype(np.float32),.01,self.hop/self.sr,real_frames)>.5
        aligned[uv_aligned]=0
        norm,uv=norm_interp_f0(aligned)
        norm=np.pad(norm,(0,frames-real_frames));uv=np.pad(uv,(0,frames-real_frames))
        f=torch.from_numpy(norm).float().unsqueeze(0);u=torch.from_numpy(uv).long().unsqueeze(0)
        pitch=f0_to_coarse(denorm_f0(f,u))
        mel=self.mel(torch.from_numpy(wav)).float()
        mel=torch.nn.functional.pad(mel,(0,0,0,max(0,frames-mel.shape[1])))[:,:frames]
        non_padding=torch.arange(frames)[None,:]<real_frames
        mel=mel*non_padding[:,:,None]
        wb=self.word(mel=mel[:,:,:self.wp['use_mel_bins']],pitch=pitch,uv=u,non_padding=non_padding,train=False)
        word_bd=wb['word_bd_pred']
        result=self.model(mel=mel[:,:,:self.hp['use_mel_bins']],word_bd=word_bd,pitch=pitch,uv=u,non_padding=non_padding,train=False)
        bd=result['note_bd_pred'][0,:real_frames].cpu().numpy()
        intervals=boundary2Interval(bd)
        count=int(result['note_lengths'][0]);pred=result['note_pred'][0,:count].cpu().numpy()
        # Zeroing masked final padding can expose an unused note after real audio.
        assert len(intervals)<=len(pred)
        probs=torch.softmax(result['note_logits'][0,:len(intervals)],-1).cpu().numpy()
        events=[]
        for i,((a,z),note) in enumerate(zip(intervals,pred)):
            start=round(a*self.hop*1000/self.sr);end=min(round(z*self.hop*1000/self.sr),len(pcm16)//16)
            if end>start:events.append({'start_ms':start,'duration_ms':end-start,'midi':int(note),
                'confidence':float(probs[i,int(note)])})
        return events,{'f0':f0,'note_boundary':bd,'word_boundary':word_bd[0,:real_frames].cpu().numpy()}

    def recognize(self,pcm16,progress=lambda *args:None):
        """Silence-aware context chunks, not independent hard 40-second windows.
        A cut can only join two clipped halves of the same predicted note; a
        genuine same-key reattack or any predicted rest is never bridged.
        """
        assert pcm16.dtype==np.float32 and np.isfinite(pcm16).all()
        length=len(pcm16)//16
        frame=320
        energy=np.array([np.sqrt(np.mean(pcm16[i:i+frame].astype(float)**2)) for i in range(0,len(pcm16),frame)])
        floor=max(.001,float(np.quantile(energy,.9))*.06)
        quiet=energy<floor
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
            # Pick a natural low-energy gap closest to a moderate context size.
            cut=min(runs,key=lambda x:abs((x[0]+x[1])*10-(cuts[-1]+18000))) if runs else None
            cuts.append(round((cut[0]+cut[1])*10) if cut else cuts[-1]+18000)
        cuts.append(length)
        all_events=[];traces=[];starts=time.perf_counter()
        for idx,(a,z) in enumerate(zip(cuts,cuts[1:])):
            begin=max(0,a-1200);end=min(length,z+1200)
            raw,trace=self.infer_chunk(pcm16[begin*16:end*16])
            core=[]
            for n in raw:
                s=n['start_ms']+begin;e=s+n['duration_ms']
                if min(e,z)<=max(s,a):continue
                core.append({**n,'start_ms':max(s,a),'duration_ms':min(e,z)-max(s,a),
                    'left_context_cut':s<a-80,'right_context_cut':e>z+80})
            if all_events and core:
                prev=all_events[-1];new=core[0]
                if prev.get('right_context_cut') and new.get('left_context_cut') and prev['midi']==new['midi'] and prev['start_ms']+prev['duration_ms']==new['start_ms']:
                    prev['duration_ms']+=new['duration_ms'];prev['right_context_cut']=new['right_context_cut'];core=core[1:]
            all_events+=core
            traces.append({'begin_ms':begin,'core_start_ms':a,'core_end_ms':z,'context_end_ms':end,
                'events':len(raw),'f0':trace['f0'].tolist(),'word_boundary_frames':np.flatnonzero(trace['word_boundary']).tolist(),
                'note_boundary_frames':np.flatnonzero(trace['note_boundary']).tolist()})
            progress(idx+1,len(cuts)-1)
        # Only the model's learned explicit rest class is omitted. No fixed
        # pitch range, duration, key, lyric or old-score filter is imposed.
        notes=[{k:v for k,v in n.items() if k in ['start_ms','duration_ms','midi','confidence']} for n in all_events if n['midi']>0]
        return notes,{'chunks':traces,'runtime_seconds':time.perf_counter()-starts,'weights_sha256':self.weights,
            'sample_rate':16000,'source_ms':length,'explicit_rest_events':sum(n['midi']==0 for n in all_events),
            'profile':self.profile,'note_bd_threshold':self.hp['note_bd_threshold'],
            'word_bd_threshold':self.wp['word_bd_threshold'],
            'software':'official ROSVOT+RWBD+RMVPE weights; CPU adapter; 1.2s context; no lyric conditions'}
