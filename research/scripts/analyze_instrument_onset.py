"""Create equal-gain A/B previews from actual Icarus sample captures."""
from pathlib import Path
import hashlib,json,subprocess,wave
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/onset_20261027';SR=48000
def capture(name):
    path=OUT/(name+'.hex')
    rows=[line.split() for line in path.read_text().splitlines()]
    assert len(rows)==240000,(name,len(rows))
    a=np.array([[int(r[0],16),int(r[1],16),int(r[2]),int(r[3])] for r in rows],dtype=np.int64)
    a[:,:2]=np.where(a[:,:2]>=32768,a[:,:2]-65536,a[:,:2])
    return a
old=capture('before');new=capture('after_quadratic')
scale=.72/max(abs(old[:,:2]).max(),abs(new[:,:2]).max())
def write(name,a):
    path=OUT/(name+'.wav')
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(SR)
        output.writeframes(np.rint(a*scale*32767).astype('<i2').tobytes())
    mp3=path.with_suffix('.mp3')
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-codec:a','libmp3lame','-q:a','2',str(mp3)],check=True)
    return str(mp3)
results={'sample_rate':SR,'preview_common_gain':float(scale),'hardware_listening':'pending','measurements':[]}
fig,axes=plt.subplots(2,2,figsize=(11,6),sharex=True)
for kind,(name,base) in enumerate([('harmonica',0),('erhu',120000)]):
    for engine,(label,column) in enumerate([('live32',0),('offline',1)]):
        env_col=column+2;start=base+43200;end=start+3000
        old_peak=int(old[start:end,env_col].max());new_peak=int(new[start:end,env_col].max())
        steady=slice(start+4800,start+9600)
        # Do not disguise a timbre/volume regression by normalizing previews separately.
        np.testing.assert_array_equal(old[steady,column],new[steady,column])
        first=np.flatnonzero(new[base+4800:base+24000,column])
        assert len(first) and first[0]<48
        target=30000 if kind==0 else 28000
        assert new_peak==target
        results['measurements'].append(dict(timbre=name,engine=label,
            old_envelope_peak=old_peak,new_envelope_peak=new_peak,
            steady_samples_identical=True,first_nonzero_sample_ms=float(first[0]*1000/SR)))
        ax=axes[kind,engine];stop=start+int(.025*SR)
        t=np.arange(stop-start)*1000/SR
        ax.plot(t,old[start:stop,env_col],label='Before',color='#a9413a')
        ax.plot(t,new[start:stop,env_col],label='After',color='#007c78')
        ax.axhline(target,color='#888888',ls=':',lw=.8)
        ax.set_title(name+' / '+label);ax.set_ylabel('Amplitude envelope');ax.set_xlabel('Time from note-on (ms)');ax.grid(alpha=.2);ax.legend()
    lo=slice(base,base+120000)
    results[name+'_ab']=write(name+'_before_then_after',np.concatenate([old[lo,0],np.zeros(24000),new[lo,0]]))
results['live_preview']=write('smooth_onset_live_harmonica_erhu',new[:,0])
results['offline_preview']=write('smooth_onset_offline_harmonica_erhu',new[:,1])
fig.tight_layout();fig.savefig(OUT/'onset_envelopes.png',dpi=170);plt.close(fig)
results['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    for p in ['rtl/synth_voice.v','rtl/poly_synth32_tm.v','tb/tb_instrument_onset_capture.v']}
(OUT/'audio_metrics.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,indent=2),flush=True)
