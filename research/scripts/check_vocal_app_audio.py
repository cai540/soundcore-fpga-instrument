"""Run actual compiled App classes on the two real demos, with a Python oracle.
The oracle is a software comparison, not a ground-truth transcription score.
"""
from pathlib import Path
import argparse,subprocess,sys,os,json,csv,hashlib,wave,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/vocal_app_20261028'
p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');args=p.parse_args()
source_dir=ROOT/'output/recording_demo_vocals_20261028'
sources=[('tigers',next(source_dir.glob('*30秒.mp3'))),('twinkle',next(source_dir.glob('*35.8秒.mp3')))]
inputs=[]
for name,source in sources:
 d=OUT/'real_audio'/name;d.mkdir(parents=True,exist_ok=True)
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-af','pan=mono|c0=0.5*c0+0.5*c1',
  '-ac','1','-f','f32le',str(d/'input.f32')],check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=sample_rate','-of','json',str(source)]))
 inputs.append({'name':name,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
  'sample_rate':int(probe['streams'][0]['sample_rate']),'directory':str(d)})
(OUT/'real_inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2),encoding='utf-8')
if args.prepare_only:print('Prepared real audio fixtures');sys.exit(0)

sys.path.insert(0,str(ROOT/'build/mono_audition_vocals3_20261028/python_deps'))
os.environ['NUMBA_CACHE_DIR']=str(OUT/'numba_cache')
import librosa
jdk=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
classes=ROOT/'app/android/app/build/tmp/kotlin-classes/debug'
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
cp=os.pathsep.join(map(str,[classes,stdlib,OUT]))
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-cp',cp,str(OUT/'CheckVocalAudio.java')],check=True)
DEST=ROOT/'output/vocal_app_20261028';DEST.mkdir(parents=True,exist_ok=True)
results=[]
for item in inputs:
 d=Path(item['directory'])
 run=subprocess.run([str(jdk/'java.exe'),'-cp',cp,'CheckVocalAudio',str(d),str(item['sample_rate'])],
  capture_output=True,text=True,encoding='utf-8',errors='replace')
 (d/'android_run.log').write_text(run.stdout+run.stderr,encoding='utf-8')
 print(run.stdout+run.stderr,flush=True);assert run.returncode==0
 audio=np.fromfile(d/'analysis.f32',dtype='<f4')
 reference_key={'pcm_sha256':hashlib.sha256(audio.tobytes()).hexdigest(),'fmin':65.4,'fmax':2100,
  'sample_rate':16000,'window':1024,'hop':160,'transition_rate':20,'librosa_version':librosa.__version__}
 ref=d/'python_reference.npz';key_file=d/'python_reference_key.json'
 if ref.exists() and key_file.exists() and json.loads(key_file.read_text())==reference_key:
  cached=np.load(ref);truth=cached['pitch'];voiced=cached['voiced'];prob=cached['probability']
 else:
  f0,voiced,prob=librosa.pyin(audio,fmin=65.4,fmax=2100,sr=16000,frame_length=1024,hop_length=160,
   max_transition_rate=20,fill_na=np.nan)
  truth=librosa.hz_to_midi(f0)
  np.savez(ref,pitch=truth,voiced=voiced,probability=prob)
  key_file.write_text(json.dumps(reference_key),encoding='utf-8')
 app=np.genfromtxt(d/'android_track.csv',delimiter=',',names=True)
 observed=app['midi']
 assert len(observed)==len(truth)
 both=np.isfinite(observed)&np.isfinite(truth)
 agreement=float(np.mean(np.abs(observed[both]-truth[both])<.11))
 voiced_match=float(np.mean(np.isfinite(observed)==voiced))
 meta=json.loads((d/'android_score.json').read_text())
 notes=list(csv.DictReader((d/'android_notes.csv').open()))
 assert int(notes[-1]['start_ms'])+int(notes[-1]['duration_ms'])>len(audio)/16-3500
 assert all(int(n['duration_ms'])>=60 for n in notes)
 assert all(int(a['start_ms'])+int(a['duration_ms'])<=int(b['start_ms']) for a,b in zip(notes,notes[1:]))
 raw=np.fromfile(d/'preview.s16',dtype='<i2')
 pcm=np.zeros(len(audio),dtype='<i2');offset=meta['first_ms']*16
 pcm[offset:min(len(pcm),offset+len(raw))]=raw[:max(0,min(len(raw),len(pcm)-offset))]
 title='两只老虎' if item['name']=='tigers' else '小星星'
 wav=DEST/(title+'_新版App识别试听.wav')
 with wave.open(str(wav),'wb') as w:w.setparams((1,2,16000,len(pcm),'NONE','not compressed'));w.writeframes(pcm.tobytes())
 mp3=wav.with_suffix('.mp3')
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-c:a','libmp3lame','-q:a','2',str(mp3)],check=True)
 results.append({**item,**meta,'pitch_agreement_with_same_config_python':agreement,
  'voiced_frame_agreement_with_python':voiced_match,'compared_voiced_frames':int(both.sum()),
  'manual_transcription_accuracy_measured':False,'preview':str(mp3)})
 print(json.dumps(results[-1],ensure_ascii=False),flush=True)
(OUT/'real_audio_validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'audio_capture_sources.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
 for p in (ROOT/'app/android/app/src/main/java/cn/soundcore/instrument').glob('*.kt')},indent=2),encoding='utf-8')
assert all(x['pitch_agreement_with_same_config_python']>.98 and x['voiced_frame_agreement_with_python']>.97 for x in results)
