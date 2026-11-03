"""Reusable acoustic evidence for a syllable-first singing decoder.

RWBD supplies phonetic boundary likelihoods; FCPE and RMVPE supply separate
pitch observations. Neither lyrics nor a target score are accepted here.
"""
from pathlib import Path
import sys,math,json,hashlib
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029'
sys.path.insert(0,str(R/'build/vocal_syllable_main_20261029/extra'))
sys.path.insert(0,str(B/'ROSVOT'))
import torch,yaml
from scipy.signal import resample_poly
from modules.rosvot.rosvot import WordbdExtractor
from modules.pe.rmvpe import RMVPE
from utils.commons.ckpt_utils import load_ckpt
from utils.commons.hparams import hparams as global_hparams
from utils.audio.mel import MelNet
from utils.audio.pitch_utils import norm_interp_f0,denorm_f0,f0_to_coarse,resample_align_curve
from torchfcpe import spawn_bundled_infer_model
from game_vocal_engine import context_cuts

class SyllableEvidenceExtractor:
    def __init__(self):
        torch.set_num_threads(6)
        self.hp=yaml.safe_load((B/'ROSVOT/checkpoints/rosvot/config.yaml').read_text(encoding='utf8'))
        self.wp=yaml.safe_load((B/'ROSVOT/checkpoints/rwbd/config.yaml').read_text(encoding='utf8'))
        global_hparams.clear();global_hparams.update(self.hp)
        self.word=WordbdExtractor(self.wp).eval()
        load_ckpt(self.word,str(B/'ROSVOT/checkpoints/rwbd/model.pt'),verbose=False)
        self.rmvpe=RMVPE(str(B/'ROSVOT/checkpoints/rmvpe/model.pt'),device='cpu')
        self.mel=MelNet(self.hp);self.mel.to('cpu')
        self.fcpe=spawn_bundled_infer_model(device='cpu')

    @torch.inference_mode()
    def infer_chunk(self,pcm):
        # Retain the native pitch range; the previous 900 Hz postfilter is
        # suitable for its training setup but must not censor soprano evidence.
        f0=self.rmvpe.infer_from_audio(pcm,sample_rate=16000)
        wav=resample_poly(pcm,3,2).astype(np.float32)
        real_frames=math.ceil(len(wav)/128);frames=math.ceil(real_frames/16)*16
        # Word network keeps its documented conditioning, separate from output F0.
        conditioned=self.rmvpe.postprocess(f0.copy(),50,900,min_gap=6)
        aligned=resample_align_curve(conditioned,.01,128/24000,real_frames)
        uv=resample_align_curve((conditioned==0).astype(np.float32),.01,128/24000,real_frames)>.5
        aligned[uv]=0;norm,uv=norm_interp_f0(aligned)
        norm=np.pad(norm,(0,frames-real_frames));uv=np.pad(uv,(0,frames-real_frames))
        f=torch.tensor(norm,dtype=torch.float32)[None,:];u=torch.tensor(uv,dtype=torch.long)[None,:]
        pitch=f0_to_coarse(denorm_f0(f,u))
        mel=self.mel(torch.from_numpy(wav)).float()
        mel=torch.nn.functional.pad(mel,(0,0,0,max(0,frames-mel.shape[1])))[:,:frames]
        mask=torch.arange(frames)[None,:]<real_frames;mel=mel*mask[:,:,None]
        wb=self.word(mel=mel[:,:,:self.wp['use_mel_bins']],pitch=pitch,uv=u,non_padding=mask,train=False)
        word=torch.sigmoid(wb['word_bd_logits'])[0,:real_frames].cpu().numpy()
        # Official FCPE latent decoder, without its optional high-note clamp.
        sample=torch.from_numpy(pcm)[None,:,None]
        latent=self.fcpe.model(self.fcpe.wav2mel(sample,16000))
        cents=self.fcpe.model.latent2cents_local_decoder(latent,threshold=.006)
        fcpe=(10*torch.pow(2.,cents/1200))[0,:,0].cpu().numpy()
        confidence=latent.max(dim=-1).values[0].cpu().numpy()
        return f0,fcpe,confidence,word

    def extract(self,pcm,progress=lambda *args:None):
        assert pcm.dtype==np.float32 and pcm.ndim==1 and np.isfinite(pcm).all()
        length=len(pcm)//16;T=(length+9)//10;cuts=context_cuts(pcm)
        arrays={k:np.zeros(T,np.float32) for k in ['rmvpe','fcpe','fcpe_confidence','word']}
        for i,(a,z) in enumerate(zip(cuts,cuts[1:])):
            begin=max(0,a-1200);end=min(length,z+1200)
            f,c,conf,w=self.infer_chunk(pcm[begin*16:end*16])
            grid=np.arange((a+9)//10,min((z+9)//10,T));local=grid*10-begin
            for key,values,step in [('rmvpe',f,10),('fcpe',c,10),('fcpe_confidence',conf,10),('word',w,128/24)]:
                # FCPE's bundled 160-sample hop is exactly 10ms. No stretch.
                j=np.rint(local/step).astype(int).clip(0,len(values)-1);arrays[key][grid]=values[j]
            progress(i+1,len(cuts)-1)
        return arrays

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--only',default='');a=p.parse_args()
    out=R/'build/vocal_syllable_main_20261029';out.mkdir(exist_ok=True)
    from benchmark_oss_vocals import inputs
    model=None
    for name,window,path,offset in inputs():
        key=name+'/'+window
        if a.only and a.only not in key:continue
        d=out/name/window;d.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if (d/'evidence.npz').exists() and json.loads((d/'evidence.json').read_text())['pcm_sha256']==digest:
            print('cached',key,flush=True);continue
        if model is None:model=SyllableEvidenceExtractor()
        pcm=np.fromfile(path,dtype='<f4');print('extract',key,flush=True)
        data=model.extract(pcm,lambda i,n:print(key,i,'/',n,flush=True))
        np.savez_compressed(d/'evidence.npz',**data)
        (d/'evidence.json').write_text(json.dumps({'pcm_sha256':digest,'source_ms':len(pcm)//16,'input_file':str(path),
            'offset_seconds':offset,'frame_ms':10,'fcpe':'official torchfcpe 0.0.4 bundled model, no high clamp',
            'no_lyrics_or_reference_inputs':True},ensure_ascii=False,indent=2),encoding='utf8')
        print('saved',key,flush=True)

if __name__=='__main__':main()
