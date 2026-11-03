"""Blind recomputation through frozen App 0.4 classes. No old score data read.

Uniform energy selection and fixed 40s windows; no manual pitch/time fixes.
Full-length preview retains the source timeline and is NOT one uploadable score.
"""
from pathlib import Path
import csv,datetime,hashlib,json,os,shutil,subprocess,wave,zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'build/generic_four_vocals_20261028';OUT=ROOT/'output/generic_four_vocals_20261028'
B.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
JDK=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
APP=ROOT/'app/android/app/build/tmp/kotlin-classes/debug'
expected=json.loads((ROOT/'build/melody_workbench_20261028/audio_class_sha256.json').read_text(encoding='utf8'))
for name,digest in expected.items():assert sha(ROOT/name)==digest,'Current classes differ from tested 0.4: '+name
release=json.loads((ROOT/'build/melody_workbench_20261028/release.json').read_text(encoding='utf8'))
assert sha(Path(release['apk']))==release['apk_sha256']
frozen=B/'frozen_classes'
if not frozen.exists():shutil.copytree(APP,frozen)
for name,digest in expected.items():assert sha(frozen/Path(name).relative_to(APP.relative_to(ROOT)))==digest
class_hashes={p.relative_to(frozen).as_posix():sha(p) for p in frozen.rglob('*') if p.is_file()}
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
cp=os.pathsep.join(map(str,[frozen,stdlib,B]))
shutil.copy2(ROOT/'scripts/support/CheckGenericVocal.java',B/'CheckGenericVocal.java')
subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-cp',cp,str(B/'CheckGenericVocal.java')],check=True)
sources=[
 ('zuguo','我和我的祖国','wodezuguo_vocals_20261026.mp3','audio [vocals] (2).mp3'),
 ('qiansixi','牵丝戏','qiansixi_vocals_20261026.mp3','audio [vocals] (1).mp3'),
 ('lantingxu','兰亭序','lantingxu_vocals_20261026.mp3','audio [vocals].mp3'),
 ('chilege','敕勒歌','chilege_vocals_20261026.wav','谭维维-敕勒歌_vocals.wav')]
config={'window_seconds':40,'first_selection':'first 500ms window with >=65% 20ms RMS frames above max(0.0025,95th-percentile RMS*0.15); add 150ms lead',
 'input_mode':'VOCAL','parameter_changes':False,'old_scores_midi_lyrics_read':False,'post_pitch_or_rhythm_correction':False,
 'raw_preview':'same 12ms/18ms sine envelope as MelodyWire, direct recognized MIDI values; no key folding',
 'app_preview':'actual MelodyWire.preview and score.events(suggestedTranspose); explicit failure if span too wide',
 'full_output':'independent 40s windows on original timeline; not one device score'}
(B/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')

def pcm_file(path,start=None,duration=None,rate=None):
 cmd=['ffmpeg','-v','error','-i',str(path)]
 if start is not None:cmd+=['-ss',f'{start:.6f}','-t',f'{duration:.6f}']
 cmd+=['-ac','1']
 if rate:cmd+=['-ar',str(rate)]
 return subprocess.check_output(cmd+['-f','f32le','-'])

def mp3(samples,path):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix('.wav')
 with wave.open(str(temp),'wb') as w:
  w.setnchannels(1 if samples.ndim==1 else samples.shape[1]);w.setsampwidth(2);w.setframerate(16000);w.writeframes(samples.astype('<i2').tobytes())
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(temp),'-c:a','libmp3lame','-q:a','2',str(path)],check=True)

def midi(notes,path):
 def vlq(n):
  a=[n&127]
  while n>127:n>>=7;a.insert(0,(n&127)|128)
  return bytes(a)
 ev=[]
 for n in notes:
  ev.extend([(n['start_ms']*2,1,n['midi']),((n['start_ms']+n['duration_ms'])*2,0,n['midi'])])
 track=bytearray(b'\0\xff\x51\x03\x07\xa1\x20');last=0
 for time,on,pitch in sorted(ev):
  track+=vlq(time-last)+bytes([0x90 if on else 0x80,pitch,88 if on else 0]);last=time
 track+=b'\0\xff\x2f\0'
 path.write_bytes(b'MThd\0\0\0\x06\0\0\0\x01\x03\xe8MTrk'+len(track).to_bytes(4,'big')+track)

def process(source,rate,directory,start,duration):
 directory.mkdir(parents=True,exist_ok=True)
 (directory/'input.f32').write_bytes(pcm_file(source,start,duration))
 run=subprocess.run([str(JDK/'java.exe'),'-Xmx512m','-cp',cp,'CheckGenericVocal',str(directory),str(rate)],
  capture_output=True,text=True,encoding='utf8',errors='replace')
 (directory/'run.log').write_text(run.stdout+run.stderr,encoding='utf8')
 if run.returncode:
  return {'start_seconds':start,'duration_seconds':duration,'recognized':False,'error':run.stderr[-1500:]},[],np.zeros(round(duration*16000),dtype='<i2')
 info=json.loads((directory/'result.json').read_text(encoding='utf8'))
 rows=list(csv.DictReader((directory/'notes.csv').open(encoding='utf8')))
 notes=[{'start_ms':int(n['start_ms']),'duration_ms':int(n['duration_ms']),'midi':int(n['midi']),'confidence':float(n['confidence'])} for n in rows]
 info.update(start_seconds=start,duration_seconds=duration,recognized=True,input_pcm_sha256=sha(directory/'input.f32'))
 info['short_notes_under_160ms']=sum(n['duration_ms']<160 for n in notes)
 info['large_fast_changes']=sum(abs(a['midi']-n['midi'])>=5 and min(a['duration_ms'],n['duration_ms'])<250
  and n['start_ms']-a['start_ms']-a['duration_ms']<=100 for a,n in zip(notes,notes[1:]))
 return info,notes,np.fromfile(directory/'original_pitch.s16',dtype='<i2')

results=[]
for name,title,filename,download in sources:
 source=ROOT/'songs/source'/filename;original=Path('C:/Users/YOUR_USER/Downloads')/download
 assert sha(source)==sha(original),'Archive is not the supplied original voice file'
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','format=duration:stream=sample_rate','-of','json',str(source)]))
 rate=int(probe['streams'][0]['sample_rate']);duration=float(probe['format']['duration'])
 audio=np.frombuffer(pcm_file(source,rate=16000),dtype='<f4')
 blocks=audio[:len(audio)//320*320].reshape(-1,320);rms=np.sqrt(np.mean(blocks.astype(float)**2,axis=1))
 threshold=max(.0025,float(np.percentile(rms,95))*.15)
 strong=np.convolve((rms>=threshold).astype(float),np.ones(25)/25,mode='valid')
 found=np.flatnonzero(strong>=.65)
 first=max(0,(int(found[0])*.02-.15) if len(found) else 0)
 first=round(first,2);length=min(40.0,duration-first)
 directory=B/name;directory.mkdir(exist_ok=True);dest=OUT/title;dest.mkdir(exist_ok=True)
 info,notes,raw=process(source,rate,directory/'first40',first,length)
 print(title,'first40',json.dumps(info,ensure_ascii=False),flush=True)
 item={'name':name,'title':title,'source':str(source),'source_sha256':sha(source),'source_duration_seconds':duration,
  'source_matches_download':True,'selection_energy_threshold':threshold,'first40':info,'chunks':[]}
 if info['recognized']:
  voice=np.fromfile(directory/'first40/analysis.f32',dtype='<f4')
  original_pcm=(voice.clip(-1,1)*28000).astype('<i2')
  mp3(raw,dest/(title+'_通用算法_原调40秒.mp3'))
  mp3(np.column_stack([original_pcm,raw]),dest/(title+'_原声左_算法右40秒.mp3'))
  mp3(original_pcm,dest/(title+'_原始人声40秒.mp3'))
  midi(notes,dest/(title+'_通用算法_原调40秒.mid'))
  shutil.copy2(directory/'first40/notes.csv',dest/'首段逐音结果.csv')
  if (directory/'first40/app_adapted.s16').exists():
   adapted=np.fromfile(directory/'first40/app_adapted.s16',dtype='<i2')
   mp3(adapted,dest/(title+'_App音域适配40秒.mp3'))
   shutil.copy2(directory/'first40/app_adapted.mid',dest/(title+'_App适配.mid'))
 total=np.zeros(round(duration*16000),dtype='<i2');all_notes=[]
 for index,start in enumerate(np.arange(0,duration,40.0)):
  part=min(40.0,duration-float(start))
  if part<.25:break
  d=directory/f'chunk_{index:02}'
  chunk,n,pcm=process(source,rate,d,float(start),part);item['chunks'].append(chunk)
  offset=round(start*16000);count=min(len(pcm),len(total)-offset);total[offset:offset+count]=pcm[:count]
  all_notes.extend([{**note,'start_ms':note['start_ms']+round(start*1000),'window':index} for note in n])
  print(title,f'chunk {index+1}',chunk.get('notes',0),chunk.get('device_error',chunk.get('error','')),flush=True)
 mp3(total,dest/(title+'_全曲分段复算_原调.mp3'))
 fullvoice=(audio[:len(total)].clip(-1,1)*28000).astype('<i2')
 if len(fullvoice)<len(total):fullvoice=np.pad(fullvoice,(0,len(total)-len(fullvoice)))
 mp3(np.column_stack([fullvoice,total]),dest/(title+'_全曲原声左_算法右.mp3'))
 midi(all_notes,dest/(title+'_全曲分段复算_原调.mid'))
 with (dest/'全曲逐音结果.csv').open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence','window']);w.writeheader();w.writerows(all_notes)
 item['total_notes']=len(all_notes);item['unrecognized_windows']=sum(not c['recognized'] for c in item['chunks'])
 item['device_incompatible_windows']=sum(c.get('recognized',False) and bool(c.get('device_error')) for c in item['chunks'])
 results.append(item)
 (B/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 print(title,'complete',len(all_notes),'notes',flush=True)

for name,digest in expected.items():assert sha(ROOT/name)==digest,'App classes changed during recomputation'
assert all(sha(frozen/p)==digest for p,digest in class_hashes.items())
record={'created':datetime.datetime.now().astimezone().isoformat(),'algorithm_apk_sha256':release['apk_sha256'],
 'algorithm_version':release['version'],'config':config,'class_sha256':class_hashes,'sources':results,
 'old_score_midi_lyrics_used':False,'app_or_firmware_modified':False,'sram_written':False,'flash_written':False,
 'human_note_accuracy_measured':False,'physical_microphone_verified':False}
(B/'release.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(B/'release.json',OUT/'复算记录.json')
lines=['# 四首原始人声：0.4通用算法复算','',
 '直接使用冻结的0.4 App编译类，从原始人声音频重新识别。没有读取旧MIDI、简谱、歌词时序或人工修订曲谱，没有改变识别参数，没有逐音修音或拉伸节奏。',
 '', '| 曲目 | 首段在原文件中的时间 | 识别音符 | 原音域MIDI | App整体移调 | 设备事件状态 |', '|---|---|---:|---|---|---|']
for s in results:
 i=s['first40'];a=i['start_seconds'];b=a+i['duration_seconds']
 lines.append(f"| {s['title']} | {a:.2f}–{b:.2f}秒 | {i.get('notes','未识别')} | {i.get('low_midi','—')}–{i.get('high_midi','—')} | {i.get('transpose','—')}半音 | {i.get('device_error') or '可生成40秒设备事件'} |")
lines+=['','## 听哪个文件','',
 '- “通用算法_原调40秒”：算法直接输出音高，保留原调。电子参考音用于听旋律，不模拟口琴或二胡。',
 '- “原声左_算法右40秒”：耳机左边是同一片段原声，右边是识别旋律，时间轴一致。',
 '- “App音域适配40秒”：实际MelodyWire.preview输出，只做App的整体移调；如35音跨度不满足，则不会伪造可上传版本。',
 '- “全曲分段复算”：原文件每40秒单独识别后按原时间轴拼接，包含前奏/间奏空白，未经人工优化；窗口边缘可能额外断音，不能当成一次整曲识别或超过40秒的设备上传。',
 '', '文件里的“全曲”指覆盖所提供的人声文件全长，不是以前剪掉前奏/间奏的演示曲谱。重新计算结果与以前精修曲目不同是正常的；短音、跳进和漏音统计只是风险提示，未经人工听审不报识别准确率。',
 '', '本轮没有修改App、内置曲目或固件，没有烧录。']
(OUT/'先读我.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for p in B.glob('*.json'):shutil.copy2(p,evidence/p.name)
for source in results:
 d=B/source['name']
 for p in d.rglob('*'):
  if p.is_file() and p.suffix in ['.csv','.json','.log','.bin']:
   target=evidence/source['name']/p.relative_to(d);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
shutil.copy2(ROOT/'scripts/recompute_four_vocals.py',evidence/'recompute_four_vocals.py')
shutil.copy2(ROOT/'scripts/support/CheckGenericVocal.java',evidence/'CheckGenericVocal.java')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files};(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'四首人声_通用算法复算试听.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p,digest in manifest.items():assert hashlib.sha256(z.read(p)).hexdigest()==digest
print(json.dumps({'output':str(OUT),'package':str(archive),'sources':len(results),'class_hash_verified':True,'old_scores_used':False},ensure_ascii=False,indent=2),flush=True)
