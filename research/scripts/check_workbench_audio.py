from pathlib import Path
import os,subprocess,shutil,json,hashlib
r=Path(__file__).resolve().parents[1];b=r/'build/melody_workbench_20261028';j=Path(r'D:\FPGA\_Tools\android\jdk\jdk-17.0.20.1+1\bin')

stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
cp=os.pathsep.join(map(str,[r/'app/android/app/build/tmp/kotlin-classes/debug',stdlib,b]))
classes=r/'app/android/app/build/tmp/kotlin-classes/debug/cn/soundcore/instrument'
prefixes=['MelodyRecognition','StablePitchTracker','VocalNoteSegmentation','PcmResampler','Protocol','ScoreTransfer']
used_classes=[p for p in classes.glob('*.class') if any(p.name.startswith(n) for n in prefixes)]
fingerprints={p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in used_classes}
shutil.copy2(r/'scripts/support/CheckVocalAudio.java',b/'CheckVocalAudio.java')
subprocess.run([str(j/'javac.exe'),'-encoding','UTF-8','-cp',cp,str(b/'CheckVocalAudio.java')],check=True)
sources=[('tigers',r/'output/recording_demo_vocals_20261028/两只老虎_30秒.mp3',0,None),('twinkle',r/'output/recording_demo_vocals_20261028/小星星_35.8秒.mp3',0,None),('tigers_holdout',Path(r'C:\Users\YOUR_USER\Downloads\audio [vocals] (3).mp3'),60,30),('twinkle_holdout',Path(r'C:\Users\YOUR_USER\Downloads\audio [vocals] (4).mp3'),65,35)]
results=[]
for name,p,start,duration in sources:
 d=b/'real_audio'/name;d.mkdir(parents=True,exist_ok=True)
 cmd=['ffmpeg','-v','error','-y','-i',str(p)]
 if duration:cmd+=['-ss',str(start),'-t',str(duration)]
 subprocess.run(cmd+['-ac','1','-f','f32le',str(d/'input.f32')],check=True)
 rate=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=sample_rate','-of','json',str(p)]))['streams'][0]['sample_rate']
 run=subprocess.run([str(j/'java.exe'),'-cp',cp,'CheckVocalAudio',str(d),str(rate)],capture_output=True,text=True,encoding='utf8')
 (d/'app_run.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stderr
 meta=json.loads((d/'android_score.json').read_text());results.append({'name':name,'source':str(p),'start':start,'duration':duration,'held_out_same_source':duration is not None,**meta})
 print(name,meta,flush=True)
(b/'real_audio_checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
assert all(hashlib.sha256((r/p).read_bytes()).hexdigest()==h for p,h in fingerprints.items()),'Compiled classes changed during audio capture'
(b/'audio_class_sha256.json').write_text(json.dumps(fingerprints,indent=2),encoding='utf8')
