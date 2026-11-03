from pathlib import Path
import csv,hashlib,json,subprocess,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/timbre_pressure_repair_20261101'
RATE=48000
def capture(name):
    x=np.array([int(v,16) for v in (OUT/name).read_text().split()],dtype=np.int32)
    assert len(x)==576000
    return np.where(x>=32768,x-65536,x).astype(float)
old,new,tonal=(capture(n) for n in ['before.hex','after.hex','tonal.hex'])
assert max(np.max(abs(x)) for x in [old,new,tonal])<32760
gain=.82*32767/max(np.max(abs(old)),np.max(abs(new)))
rms=lambda x:float(np.sqrt(np.mean(x*x)))
previews={};measure=[]
def write(name,data):
    file=OUT/(name+'.wav')
    pcm=np.rint(data*gain).astype('<i2')
    with wave.open(str(file),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(RATE);stream.writeframes(pcm.tobytes())
    mp3=file.with_suffix('.mp3')
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(file),'-c:a','libmp3lame','-q:a','2',str(mp3)],check=True)
    decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(mp3),'-f','s16le','-'])
    assert len(decoded)==len(pcm)*2
    return {'file':str(mp3),'seconds':len(pcm)/RATE,'sha256':hashlib.sha256(mp3.read_bytes()).hexdigest()}
for index,name in enumerate(['harmonica','erhu']):
    a=index*288000;b=a+288000
    assert np.max(abs(new[a:a+4500]))==0,'idle sound before onset'
    previews[name+'_AB']=write(name+'_before_then_after',np.r_[old[a:b],np.zeros(24000),new[a:b]])
    previews[name+'_new']=write(name+'_new',new[a:b])
    s=slice(a+80000,a+100000)
    noise=rms(new[s]-tonal[s])/rms(new[s]);assert noise<.002,'random texture still exceeds0.2%'
    level_change=20*np.log10(rms(new[s])/rms(old[s]));assert abs(level_change)<.65,'overall gain masks the tone change'
    measure.append({'instrument':name,'strong_window_rms_change_db':level_change,
        'random_component_rms_fraction':noise,'no_clipping':True,'idle_silence':True})

rows=list(csv.DictReader((OUT/'texture_levels.csv').open()))
assert len(rows)==630
levels=[]
for timbre in [0,1]:
    values=[float(r['rms']) for r in rows if int(r['timbre'])==timbre]
    spread=20*np.log10(max(values)/min(values));assert spread<1
    levels.append({'timbre':timbre,'cases':len(values),'rms_span_db':float(spread)})
coeff=[int(v,16) for v in (ROOT/'rtl/expression_normalized.mem').read_text().split()]
old_coeff=[int(v,16) for v in (OUT/'before/rtl/expression_normalized.mem').read_text().split()]
def harmonics(table,timbre):
    values=[[((n>>(h*12))&4095) for h in range(6)] for n in table[timbre*315:(timbre+1)*315]]
    return {'max_h2_over_fundamental':max(v[1]/v[0] for v in values),'max_h3_over_fundamental':max(v[2]/v[0] for v in values)}
spectra={name:{'before':harmonics(old_coeff,t),'after':harmonics(coeff,t)} for t,name in [(0,'erhu'),(1,'harmonica')]}
assert spectra['harmonica']['after']['max_h2_over_fundamental']<.55
assert spectra['harmonica']['after']['max_h3_over_fundamental']<.25
result={'real_verilog_capture':True,'path':'same mono voice/envelope/texture used for offline playback; full32voice deadline checked separately',
    'sample_rate':RATE,'common_preview_gain':gain,'previews':previews,'measurements':measure,'spectral_630_cases':levels,
    'harmonic_ratios':spectra,'random_texture_nominal_gain_change_db':-24.0824,
    'physical_listening_verified':False,'real_instrument_similarity_verified':False,'fpga_programmed':False}
(OUT/'audio_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'measurements':measure,'spectral':levels,'harmonics':spectra},ensure_ascii=False,indent=2))
