from pathlib import Path
import hashlib,json,os,subprocess,wave
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/expression_20261028'
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
target=OUT/'audition.vvp'
c=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s','tb_expression_audition','-o',str(target),
    *[str(ROOT/p) for p in ['tb/tb_expression_audition.v','rtl/synth_voice.v','rtl/note_step_table35.v',
        'rtl/instrument_texture.v','rtl/expressive_texture.v','rtl/pressure_expression32.v']]],capture_output=True,text=True,cwd=ROOT)
assert c.returncode==0,c.stdout+c.stderr
run=subprocess.run([str(TOOL/'vvp.exe'),str(target)],capture_output=True,text=True,cwd=ROOT,timeout=900)
(OUT/'audition.log').write_text(run.stdout+run.stderr);assert run.returncode==0 and 'PASS:' in run.stdout,run.stdout+run.stderr
signals={}
for name in ['old','continuous','spectral_raw','spectral_norm']:
    a=np.array([int(x,16) for x in (OUT/(name+'.hex')).read_text().split()],dtype=np.int32)
    assert len(a)==576000;signals[name]=np.where(a>32767,a-65536,a).astype(float)
assert max(np.max(np.abs(a)) for a in signals.values())<32760
gain=.82*32767/max(np.max(np.abs(a)) for a in signals.values())
def write(name,a):
    path=OUT/(name+'.wav')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(np.rint(a*gain).astype('<i2').tobytes())
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-codec:a','libmp3lame','-q:a','2',str(path.with_suffix('.mp3'))],check=True)
    return str(path.with_suffix('.mp3'))
previews={}
for kind,start in [('harmonica',0),('erhu',288000)]:
    region=slice(start,start+288000)
    previews[kind+'_old_then_new']=write(kind+'_old_then_new',np.concatenate([signals['old'][region],np.zeros(24000),signals['spectral_norm'][region]]))
    previews[kind+'_new']=write(kind+'_new',signals['spectral_norm'][region])
    previews[kind+'_ablations']=write(kind+'_four_ablations',np.concatenate([np.concatenate([signals[n][region],np.zeros(12000)]) for n in signals]))
    # Separately labeled RMS-matched A/B allows timbre judgment without level bias.
    a=signals['old'][region];b=signals['spectral_norm'][region]
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    matched=b*rms(a)/rms(b)
    assert np.max(abs(matched*gain))<32767
    previews[kind+'_rms_matched']=write(kind+'_RMS_matched_AB',np.concatenate([a,np.zeros(24000),matched]))
controls=np.genfromtxt(OUT/'audition_controls.csv',delimiter=',',names=True)
fig,axes=plt.subplots(2,1,figsize=(10,5.4),sharex=True)
for i,kind in enumerate(['harmonica','erhu']):
    rows=controls[controls['timbre']==i];axes[i].plot(rows['frame']/48000,rows['pressure'],label='Applied pressure',alpha=.7)
    axes[i].plot(rows['frame']/48000,rows['performance'],label='Continuous expression',lw=1.2)
    axes[i].set_title(kind+' / synthetic pressure gesture');axes[i].set_ylabel('0..255');axes[i].grid(alpha=.2);axes[i].legend(loc='upper right')
axes[-1].set_xlabel('Seconds');fig.tight_layout();fig.savefig(OUT/'expression_response.png',dpi=160);plt.close(fig)
result={'actual_rtl_source':True,'capture_path':'single-voice RTL using same expressive texture and instrument envelope; not a physical recording',
    'samples_per_ablation':576000,'sample_rate_hz':48000,'common_preview_gain':gain,
    'peak_by_variant':{n:float(np.max(abs(a))) for n,a in signals.items()},'preview_files':previews,
    'real_instrument_similarity_verified':False,'rms_matched_files_are_separately_labeled':True,
    'capture_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        ['rtl/synth_voice.v','rtl/instrument_texture.v','rtl/expressive_texture.v','rtl/pressure_expression32.v','tb/tb_expression_audition.v']}}
(OUT/'audition.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
