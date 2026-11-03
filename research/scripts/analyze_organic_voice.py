"""Compare actual old/new RTL tone, texture ablation and equal-gain previews."""
from pathlib import Path
import argparse,hashlib,json,subprocess,wave
import numpy as np
from scipy.signal import correlate
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];SR=48000
parser=argparse.ArgumentParser()
parser.add_argument('--out',default='build/organic_20261027')
parser.add_argument('--label',default='organic')
parser.add_argument('--min-texture',type=float,default=.015)
parser.add_argument('--max-texture',type=float,default=.20)
args=parser.parse_args();OUT=ROOT/args.out
def read(name):
    a=np.array([int(x,16) for x in (OUT/(name+'.hex')).read_text().split()],dtype=np.int32)
    assert len(a)==576000,(name,len(a))
    return np.where(a>32767,a-65536,a).astype(float)
old=read('old');new=read('new');tonal=read('tonal_only')
rms=lambda a:float(np.sqrt(np.mean(a*a)))
scale=.76/max(abs(old).max(),abs(new).max())
def write(name,samples):
    p=OUT/(name+'.wav')
    with wave.open(str(p),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR)
        w.writeframes(np.rint(samples*scale*32767).astype('<i2').tobytes())
    mp3=p.with_suffix('.mp3');subprocess.run(['ffmpeg','-v','error','-y','-i',str(p),'-codec:a','libmp3lame','-q:a','2',str(mp3)],check=True)
    return str(mp3)
result={'sample_rate':SR,'common_preview_gain':scale,'from_actual_rtl':True,'measurements':[],'previews':{}}
fig,axes=plt.subplots(2,2,figsize=(11,6))
for row,(kind,base) in enumerate([('harmonica',0),('erhu',288000)]):
    metrics={'timbre':kind,'levels':{}}
    for start,end,label in [(30000,90000,'soft'),(100000,175000,'strong'),(235000,270000,'held')]:
        a=old[base+start:base+end];b=new[base+start:base+end]
        db=20*np.log10(rms(b)/rms(a))
        assert abs(db)<2.0,(kind,label,'unexpected loudness jump',db)
        metrics['levels'][label]={'old_rms':rms(a),'new_rms':rms(b),'change_db':float(db)}
    held=slice(base+240000,base+274000)
    a=old[held];b=new[held];residual=b-tonal[held]
    fraction=rms(residual)/rms(b)
    assert args.min_texture<fraction<args.max_texture,(kind,'air/bow texture outside selected limits',fraction)
    assert abs(new).max()<32760,'source capture clipped'
    assert np.max(abs(new[base:base+9500]))==0,'idle noise before note'
    metrics['texture_rms_fraction']=fraction
    # A known held C5 checks tuning while retaining natural modulation.
    ac=correlate(b,b,mode='full',method='fft')[len(b)-1:]
    center=int(SR/523.2511306);lo=center-5;hi=center+6
    lag=lo+int(np.argmax(ac[lo:hi]));d=.5*(ac[lag-1]-ac[lag+1])/(ac[lag-1]-2*ac[lag]+ac[lag+1])
    hz=SR/(lag+d);assert abs(1200*np.log2(hz/523.2511306))<35
    metrics['held_pitch_hz']=float(hz)
    ax=axes[row,0]
    for sig,label,color in [(a,'Before','#ad5149'),(b,'After','#007c78')]:
        f=np.fft.rfftfreq(len(sig),1/SR);spec=abs(np.fft.rfft(sig*np.hanning(len(sig))))
        ax.plot(f,20*np.log10(np.maximum(spec,1)),label=label,color=color,lw=.8)
    ax.set_xlim(0,6000);ax.set_ylim(0,150);ax.set_title(kind+' / held C5 spectrum');ax.set_xlabel('Hz');ax.legend();ax.grid(alpha=.2)
    axes[row,1].plot(np.arange(2000)*1000/SR,residual[:2000],color='#536e91',lw=.6)
    axes[row,1].set_title(kind+' / isolated air or bow contribution');axes[row,1].set_xlabel('ms');axes[row,1].grid(alpha=.2)
    piece=slice(base,base+288000)
    result['previews'][kind+'_ab']=write(kind+'_old_then_'+args.label,np.concatenate([old[piece],np.zeros(24000),new[piece]]))
    result['previews'][kind+'_new']=write(kind+'_'+args.label+'_phrase',new[piece])
    result['measurements'].append(metrics)
result['previews']['both_new']=write(args.label+'_harmonica_and_erhu',new)
fig.tight_layout();fig.savefig(OUT/'spectral_texture_check.png',dpi=160);plt.close(fig)
result['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
    ['rtl/instrument_texture.v','rtl/synth_voice.v','tb/tb_organic_voice_capture.v']}
(OUT/'audio_metrics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
