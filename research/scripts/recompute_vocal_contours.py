"""Actual 0.9 App recognition of every source-audio chunk; no editorial input."""
from pathlib import Path
import csv,json,hashlib,subprocess,os,shutil,math
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_final_phrases_20261029'
OLD=ROOT/'build/vocal_phrase_20261029';JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
classes=ROOT/'app/android/app/build/tmp/kotlin-classes/debug/cn/soundcore/instrument'
frozen=B/'frozen_classes/cn/soundcore/instrument';frozen.mkdir(parents=True,exist_ok=True)
fingerprints={p.relative_to(ROOT).as_posix():sha(p) for p in classes.glob('*.class')}
for p in classes.glob('*.class'):shutil.copy2(p,frozen/p.name)
(B/'audio_class_sha256.json').write_text(json.dumps(fingerprints,indent=2),encoding='utf8')
cp=os.pathsep.join(map(str,[B/'frozen_classes',stdlib,B]))
for helper in ['CheckGenericVocal','CheckVocalAudio','DumpVocalContourStages']:
 subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(B),str(ROOT/f'scripts/support/{helper}.java')],check=True)
sources={'zuguo':'wodezuguo_vocals_20261026.mp3','lantingxu':'lantingxu_vocals_20261026.mp3',
 'qiansixi':'qiansixi_vocals_20261026.mp3','chilege':'chilege_vocals_20261026.wav'}
offsets={'zuguo':47.09,'lantingxu':.49,'qiansixi':23.99,'chilege':30.97}
source_meta={};tasks=[]
for name,filename in sources.items():
 src=ROOT/'songs/source'/filename
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(src)]))
 duration=float(probe['format']['duration']);source_meta[name]={'file':str(src),'sha256':sha(src),'container_seconds':duration}
 for k in range(math.ceil(duration/40)):
  tasks.append((name,f'chunk_{k:02}',src,k*40,min(40,duration-k*40),False))
 tasks.append((name,'first40',src,offsets[name],40,True))
for name in ['tigers','twinkle','tigers_holdout','twinkle_holdout']:
 tasks.append((name,'nursery',None,0,0,True))
(B/'source_audio_sha256.json').write_text(json.dumps(source_meta,ensure_ascii=False,indent=2),encoding='utf8')
results=[]
for name,window,src,offset,duration,wire in tasks:
 d=B/'audio'/name/window;d.mkdir(parents=True,exist_ok=True)
 if src:
  # Direct source decode at native 44.1k, rather than generated MIDI/model audio.
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-ss',str(offset),'-t',str(duration),
   '-ac','1','-ar','44100','-f','f32le',str(d/'input.f32')],check=True)
 else:shutil.copy2(OLD/'audio'/name/window/'input.f32',d/'input.f32')
 old=OLD/'audio'/name/window
 if (old/'input.f32').exists():assert sha(d/'input.f32')==sha(old/'input.f32'),(name,window)
 run=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp,'CheckGenericVocal',str(d),'44100'],capture_output=True,text=True,encoding='utf8')
 (d/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
 if run.returncode:
  assert '没有找到稳定人声' in run.stderr,run.stderr
  item={'name':name,'window':window,'status':'no_stable_melody','offset_seconds':offset,'new':str(d)}
 else:
  meta=json.loads((d/'result.json').read_text());item={'name':name,'window':window,'status':'ok','offset_seconds':offset,'new':str(d),**meta}
  if (old/'analysis.f32').exists():assert sha(d/'analysis.f32')==sha(old/'analysis.f32')
  trace=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp,'DumpVocalContourStages',str(d)],capture_output=True,text=True,encoding='utf8')
  (d/'stage.log').write_text(trace.stdout+trace.stderr,encoding='utf8');assert trace.returncode==0,trace.stderr
  if (old/'notes.csv').exists():
   # Every part of the old pipeline is frozen, not just selected lyric lines.
   assert (d/'stage_before_contour.csv').read_bytes()==(old/'notes.csv').read_bytes(),(name,window,'old pipeline changed')
  if wire and meta['transpose'] is not None and not meta['device_error']:
   run=subprocess.run([str(JDK/'java.exe'),'-Dfile.encoding=UTF-8','-cp',cp,'CheckVocalAudio',str(d),'44100'],capture_output=True,text=True,encoding='utf8')
   (d/'wire.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stderr
   a=list(csv.DictReader((d/'notes.csv').open()));z=list(csv.DictReader((d/'android_notes.csv').open()))
   assert [[x[k] for k in ['start_ms','duration_ms','midi']] for x in a]==[[x[k] for k in ['start_ms','duration_ms','midi']] for x in z]
   item['wire_fixture']=True
 results.append(item);(B/'audio_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 print(name,window,item.get('notes'),item['status'],flush=True)
assert all(sha(ROOT/p)==h for p,h in fingerprints.items()),'App classes changed during capture'
print('Completed',len(results),'actual-App PCM windows; no song templates supplied.',flush=True)
