"""Equal-gain audition from actual old/new RTL captures, with transparent DSP checks."""
from pathlib import Path
import argparse,json,hashlib,wave,subprocess
import numpy as np
from scipy.signal import correlate
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'build/harmonica_refinement_20261102';O=R/'output/harmonica_refinement_20261102'
RATE=48000
def rms(x):return float(np.sqrt(np.mean(np.square(x,dtype=float))))
def write_audio(name,x,gain):
    pcm=np.rint(x*gain);assert np.max(abs(pcm))<32767
    f=O/(name+'.wav')
    with wave.open(str(f),'wb')as w:w.setparams((1,2,RATE,0,'NONE','NONE'));w.writeframes(pcm.astype('<i2').tobytes())
    out=f.with_suffix('.mp3');subprocess.run(['ffmpeg','-v','error','-y','-i',str(f),'-c:a','libmp3lame','-q:a','2',str(out)],check=True)
    return dict(file=out.name,seconds=len(x)/RATE,sha256=hashlib.sha256(out.read_bytes()).hexdigest())
def highband(x):
    y=x-np.mean(x);window=np.hanning(len(y));f=np.fft.rfftfreq(len(y),1/RATE);power=np.abs(np.fft.rfft(y*window))**2
    return float(10*np.log10(power[f>=5000].sum()/power.sum()))
def main(partial=False):
    O.mkdir(parents=True,exist_ok=True);x=np.loadtxt(B/'phrase.tsv');assert x.shape==(288000,5),x.shape
    old,new,tonal=x[:,:3].T;assert np.max(abs(x[:4800,:3]))==0
    assert max(np.max(abs(old)),np.max(abs(new)))<32760
    assert x[:,3].max()<=30000
    song=None
    if not partial:song=np.loadtxt(B/'zuguo20.tsv');assert song.shape==(960000,2),song.shape
    peak=max(np.max(abs(old)),np.max(abs(new)),0 if song is None else np.max(abs(song)))
    gain=.76*32767/peak
    held=slice(244000,274000);strong=slice(48000,62000)
    fraction=rms(new[held]-tonal[held])/rms(new[held]);assert fraction<.004
    change=20*np.log10(rms(new[strong])/rms(old[strong]));assert abs(change)<.5,change
    ac=correlate(tonal[held],tonal[held],mode='full',method='fft')[len(tonal[held])-1:]
    lo,hi=85,100;k=lo+int(np.argmax(ac[lo:hi]));d=.5*(ac[k-1]-ac[k+1])/(ac[k-1]-2*ac[k]+ac[k+1]);hz=RATE/(k+d)
    cents=float(1200*np.log2(hz/523.2511306));assert abs(cents)<20
    assert len(new)==len(old) and np.max(abs(new[-2000:]))==0
    result=dict(actual_rtl_capture=True,source_path='original mono instrument synthesizer; full32voice schedule tested separately',
        sample_rate=RATE,common_gain=gain,strong_steady_rms_change_db=float(change),new_air_rms_fraction=fraction,
        held_pitch_hz=float(hz),held_pitch_error_cents=cents,no_clipping=True,idle_and_final_silence=True,
        upper_band_fraction_db_before=highband(old[held]),upper_band_fraction_db_after=highband(new[held]),
        physical_listening_verified=False,real_instrument_similarity_certified=False,previews={})
    result['raw_capture_sha256']={name:hashlib.sha256((B/name).read_bytes()).hexdigest()for name in(['phrase.tsv']if partial else['phrase.tsv','zuguo20.tsv'])}
    result['frozen_input_ledger_sha256']=hashlib.sha256((B/'frozen_inputs.json').read_bytes()).hexdigest()
    result['previews']['new']=write_audio('口琴_新版短句',new,gain)
    result['previews']['before_after']=write_audio('口琴_同增益对比_先旧后新',np.r_[old,np.zeros(24000),new],gain)
    if song is not None:
        # Presentation only: fade the final10ms of a cropped excerpt to avoid
        # a cut-mid-cycle click. Raw RTL traces and all measurements stay raw.
        envelope=np.ones(len(song));envelope[-480:]=.5*(1+np.cos(np.linspace(0,np.pi,480)))
        result['preview_excerpt_end_fade_ms']=10
        result['previews']['song_new']=write_audio('我和我的祖国_新版口琴_20秒',song[:,1]*envelope,gain)
        result['previews']['song_old']=write_audio('我和我的祖国_A623口琴_20秒',song[:,0]*envelope,gain)
    plt.rcParams.update({'font.sans-serif':['SimHei'],'axes.unicode_minus':False})
    fig,ax=plt.subplots(1,2,figsize=(11,3.8))
    for data,label,color in[(old,'A623原版','#b76a58'),(new,'A6C4新版','#0b8b7c')]:
        sig=data[held];f=np.fft.rfftfreq(len(sig),1/RATE);a=abs(np.fft.rfft(sig*np.hanning(len(sig))));db=20*np.log10(np.maximum(a,1e-9)/a.max())
        ax[0].plot(f,db,label=label,color=color,lw=.8)
    ax[0].set(xlim=(0,8000),ylim=(-95,3),xlabel='频率 / Hz',ylabel='相对幅值 / dB',title='实际RTL长音频谱（非喇叭实录）');ax[0].legend();ax[0].grid(alpha=.2)
    ax[1].plot(np.arange(2400)/48,x[4800:7200,3]/30000,color='#0b8b7c',label='新版音量包络')
    ax[1].axvline(128/48,color='#999',lw=.8,ls='--');ax[1].set(xlabel='起音后 / ms',ylabel='持续电平比例',ylim=(0,1.05),title='先柔和发声，再逐渐丰满');ax[1].grid(alpha=.2)
    fig.tight_layout();fig.savefig(O/'口琴频谱与起音.png',dpi=160);plt.close(fig)
    (B/'audio_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k!='source_path'},ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phrase-only',action='store_true');a=p.parse_args();main(a.phrase_only)
