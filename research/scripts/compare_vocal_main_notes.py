"""Recompute from PCM with actual compiled App classes. References are offline only."""
from pathlib import Path
import os,subprocess,shutil,json,hashlib,csv
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_syllable_20261029'
OLD=ROOT/'build/generic_four_vocals_20261028'
JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
classes=ROOT/'app/android/app/build/tmp/kotlin-classes/debug'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prefixes=['MelodyRecognition','MelodyNote','MelodyScore','MelodyWire','MelodyInput','VocalMainNoteSegmentation',
 'VocalNoteSegmentation','StablePitchTracker','PcmResampler','Protocol','ScoreTransfer']
files=list((classes/'cn/soundcore/instrument').glob('*.class'))
fingerprints={p.relative_to(ROOT).as_posix():sha(p) for p in files}
frozen=B/'frozen_classes/cn/soundcore/instrument';frozen.mkdir(parents=True,exist_ok=True)
for p in files:shutil.copy2(p,frozen/p.name)
cp=os.pathsep.join(map(str,[B/'frozen_classes',stdlib,B]))
for helper in ['CheckGenericVocal','CheckVocalAudio']:
 subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(B),str(ROOT/f'scripts/support/{helper}.java')],check=True)
results=[]
tasks=[]
for name in ['zuguo','chilege','qiansixi','lantingxu']:
 tasks.append((name,'first40',OLD/name/'first40',True))
for name in ['zuguo','chilege']:
 for p in sorted((OLD/name).glob('chunk_*')):tasks.append((name,p.name,p,False))
for name in ['tigers','twinkle','tigers_holdout','twinkle_holdout']:
 tasks.append((name,'nursery',ROOT/f'build/melody_workbench_20261028/real_audio/{name}',True))
for name,window,old,wire in tasks:
 d=B/'audio'/name/window;d.mkdir(parents=True,exist_ok=True)
 shutil.copy2(old/'input.f32',d/'input.f32')
 # All archived input.f32 files preserve native 44100Hz mono decode.
 run=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp,'CheckGenericVocal',str(d),'44100'],capture_output=True,text=True,encoding='utf8')
 (d/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
 if run.returncode:
  assert '没有找到稳定人声' in run.stderr,run.stderr
  results.append({'name':name,'window':window,'status':'no_stable_melody','old':str(old),'new':str(d)})
  print(name,window,'no stable melody',flush=True);continue
 metadata=json.loads((d/'result.json').read_text(encoding='utf8'))
 # Verify sample identity; do not turn a resampling difference into a quality gain.
 assert (d/'analysis.f32').read_bytes()==(old/'analysis.f32').read_bytes()
 if wire:
  run=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp,'CheckVocalAudio',str(d),'44100'],capture_output=True,text=True,encoding='utf8')
  (d/'wire.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stderr
  # Both harnesses call the same App recognizer; the canonical score must agree.
  a=list(csv.DictReader((d/'notes.csv').open()));b=list(csv.DictReader((d/'android_notes.csv').open()))
  assert [[n[k] for k in ['start_ms','duration_ms','midi']] for n in a]==[[n[k] for k in ['start_ms','duration_ms','midi']] for n in b]
 results.append({'name':name,'window':window,'status':'ok','old':str(old),'new':str(d),'wire_fixture':wire,**metadata})
 print(name,window,metadata,flush=True)
assert all(sha(ROOT/p)==h for p,h in fingerprints.items()),'Classes changed while collecting audio'
(B/'audio_class_sha256.json').write_text(json.dumps(fingerprints,indent=2),encoding='utf8')
(B/'audio_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print('Completed',len(results),'real-audio windows; no reference data is a recognizer input.')
