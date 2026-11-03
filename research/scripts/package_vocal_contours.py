"""Four source-PCM algorithm results, exported with an auditable source clock."""
from pathlib import Path
import json,csv,struct,subprocess,hashlib,shutil,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_final_phrases_20261029';O=R/'output/vocal_final_phrases_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((B/'release.json').read_text(encoding='utf8'));assert release['android_test_count']>=200
items=json.loads((B/'audio_results.json').read_text(encoding='utf8'))
titles={'zuguo':'我和我的祖国','lantingxu':'兰亭序','qiansixi':'牵丝戏','chilege':'敕勒歌'}
O.mkdir(exist_ok=True);inventory=[]
def notes(p,offset=0):
 return [{'start_ms':int(n['start_ms'])+offset,'duration_ms':int(n['duration_ms']),'midi':int(n['midi']),'confidence':float(n['confidence'])} for n in csv.DictReader(p.open(encoding='utf8'))]
def csvout(ns,p):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(ns)
def midi(ns,p):
 def var(v):
  a=[v&127]
  while v>127:v>>=7;a.insert(0,(v&127)|128)
  return bytes(a)
 tr=bytearray(b'\0\xff\x51\x03\x07\xa1\x20');cursor=0
 for n in ns:
  assert n['start_ms']>=cursor and n['duration_ms']>=20
  tr+=var((n['start_ms']-cursor)*2)+bytes([0x90,n['midi'],88])
  tr+=var(n['duration_ms']*2)+bytes([0x80,n['midi'],0]);cursor=n['start_ms']+n['duration_ms']
 tr+=b'\0\xff\x2f\0';p.write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,1000)+b'MTrk'+struct.pack('>I',len(tr))+tr)
def encode(x,p):
 channels=1 if x.ndim==1 else x.shape[1]
 subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar','16000','-ac',str(channels),'-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(p)],input=x.astype('<i2').tobytes(),check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
 duration=float(probe['format']['duration']);assert abs(duration-len(x)/16000)<.2 and int(probe['streams'][0]['channels'])==channels
 inventory.append({'file':p.relative_to(O).as_posix(),'seconds':len(x)/16000,'container_seconds':duration,'channels':channels})
for name,title in titles.items():
 out=O/title;out.mkdir(exist_ok=True)
 chunks=[x for x in items if x['name']==name and x['window'].startswith('chunk_')]
 end=max(round(x['offset_seconds']*16000)+(Path(x['new'])/'analysis.f32').stat().st_size//4 for x in chunks)
 full=np.zeros(end,dtype='<i2');voice=np.zeros(end,dtype='<i2');allnotes=[]
 for x in chunks:
  d=Path(x['new']);start=round(x['offset_seconds']*16000)
  raw=np.fromfile(d/'analysis.f32',dtype='<f4');voice[start:start+len(raw)]=(raw.clip(-1,1)*28000).astype('<i2')
  if x['status']!='ok':continue
  a=np.fromfile(d/'original_pitch.s16',dtype='<i2');full[start:start+len(a)]=a
  allnotes+=notes(d/'notes.csv',round(x['offset_seconds']*1000))
 first=allnotes[0]['start_ms'];last=allnotes[-1]['start_ms']+allnotes[-1]['duration_ms']
 csvout(allnotes,out/f'{title}_原声时间轴.csv');midi(allnotes,out/f'{title}_原声时间轴.mid')
 relative=[{**n,'start_ms':n['start_ms']-first} for n in allnotes]
 midi(relative,out/f'{title}_算法试听.mid')
 encode(full[first*16:last*16],out/f'{title}_全曲算法试听.mp3')
 encode(np.column_stack([voice[first*16:last*16],full[first*16:last*16]]),out/f'{title}_原人声左_算法右.mp3')
 f=next(x for x in items if x['name']==name and x['window']=='first40');d=Path(f['new'])
 encode(np.fromfile(d/'original_pitch.s16',dtype='<i2'),out/f'{title}_首段40秒.mp3')
 csvout(notes(d/'notes.csv'),out/f'{title}_首段40秒.csv')
 if (d/'app_adapted.mid').exists():shutil.copy2(d/'app_adapted.mid',out/f'{title}_首段设备适配.mid')
 song_info={'title':title,'source_seconds':len(full)/16000,'preview_source_begin_ms':first,'preview_source_end_ms':last,'notes':len(allnotes),
  'first40_source_begin_seconds':f['offset_seconds'],'method':'actual App code, independent <=40s original-PCM chunks, source-clock stitch',
  'unsupported_chunks':[{'window':x['window'],'reason':x.get('device_error'),'low_midi':x.get('low_midi'),'high_midi':x.get('high_midi')} for x in chunks if x.get('device_error')],
  'raw_pitch_preserved':True,'manual_note_overrides':False,'main_notes_preview_not_fpga_timbre':True}
 (out/'结果说明.json').write_text(json.dumps(song_info,ensure_ascii=False,indent=2),encoding='utf8')
 if name=='zuguo':
  old=R/'build/vocal_phrase_20261029/audio/zuguo/first40'
  encode(np.column_stack([np.fromfile(old/'original_pitch.s16',dtype='<i2'),np.fromfile(d/'original_pitch.s16',dtype='<i2')]),out/'本次修改_旧左新右_40秒.mp3')
  tail=B/'audio/zuguo/chunk_02';a=np.fromfile(tail/'original_pitch.s16',dtype='<i2')[3400*16:9400*16]
  z=np.fromfile(R/'build/vocal_phrase_20261029/audio/zuguo/chunk_02/original_pitch.s16',dtype='<i2')[3400*16:9400*16]
  encode(a,out/'路上一道辙_完整尾句6秒.mp3');encode(np.column_stack([z,a]),out/'路上一道辙_旧左新右6秒.mp3')
apk=O/'声芯_通用人声识谱_v0.9.apk';shutil.copy2(release['apk_source'],apk);assert sha(apk)==release['apk_sha256']
release['apk']=str(apk);(B/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(2,1,figsize=(12,6),layout='constrained')
for ax,win,off,begin,end,title in [(axs[0],'first40',47.09,78.3,80.6,'袅袅炊烟：前一重复音恢复下行，炊本身保持74'),(axs[1],'chunk_02',80,83.5,88.5,'路上一道辙：去除低音滑入，恢复上/道主音')]:
 d=B/'audio/zuguo'/win;rows=list(csv.DictReader((d/'vocal_frontend.csv').open()));t=np.array([float(x['ms'])/1000+off for x in rows]);p=np.array([float(x['pitch']) for x in rows]);mask=(t>=begin)&(t<=end)
 ax.plot(t[mask],p[mask],color='.75',lw=1,label='原始F0（不改）')
 for fn,color,label in [('stage_before_contour.csv','#ba7055','0.8'),('notes.csv','#008b82','0.9')]:
  for j,n in enumerate(notes(d/fn)):
   s=n['start_ms']/1000+off;e=s+n['duration_ms']/1000
   if s<end and e>begin:ax.plot([max(begin,s),min(end,e)],[n['midi']]*2,color=color,lw=2.2,label=label if j==next(i for i,q in enumerate(notes(d/fn)) if q['start_ms']/1000+off+q['duration_ms']/1000>begin) else None)
 ax.set_xlim(begin,end);ax.set_title(title,fontproperties=font);ax.set_ylabel('MIDI');ax.grid(alpha=.2);ax.legend(prop=font,ncol=3)
axs[-1].set_xlabel('原始人声文件时间 / 秒',fontproperties=font);fig.savefig(O/'两处修改对照.png',dpi=140);plt.close(fig)
report=f'''# 通用人声识谱0.9：两处修正与四曲重新计算

本轮改通用算法，从四首提供的人声文件重新运行实际App编译代码。歌名、歌词、人工简谱、旧MIDI、固定时间和文件指纹均不进入识谱推断。原精修曲库及FPGA固件不变，未烧录。

## 两处实际变化

- “路”的低音上滑原来在整文件窗口里被拆成62→64；没有独立声学起音的单调滑入现并回64，去掉一次额外低音起音。“上”在64→60之间的含糊重复现按录音推断的下行阶进恢复62。“一道辙”现为60→67→65；道的短弧形发声由有观测支持的上转折主音67表达，辙仍是稳定65。先前40秒片段会截到辙字中间，完整尾句6秒另取完整上下文窗口。
- “炊”所在位置，原声确实支持74，本轮没有为了改而把它改错。实际偏差在它前面的第二个“袅”：原77、77、74、72现为77、76、74、72，下行衔接更明确。词位仅作离线说明，不用于规则触发。
- 已认可的其余祖国片段逐帧音高、既有事件起止均保留；仅上述邻接区域变化。敕勒歌所有窗口、兰亭序/牵丝戏原首40秒、四个儿歌回归片段逐事件不变。

## 四首结果怎样使用

每首文件夹里有“全曲算法试听.mp3”、“原人声左_算法右.mp3”、原声时间轴CSV/MIDI和从首个识别音起的试听MIDI。MP3采用统一正弦主音，专供比较音高、节奏和停顿，不冒充FPGA的口琴/二胡实机音色。使用立体声耳机听对照：左声道原人声、右声道算法。

完整结果由原文件按40秒独立识别后按原时间轴接回；这是桌面全文件诊断，不是宣称手机已支持一次识别/上传整首歌。App仍限制单次40秒。完整MIDI供试听/检查，不可整首直接上传现有40秒RAM。各文件夹“结果说明.json”记录试听裁去的首尾静音量；中间停顿不压缩。最早识别音仍可能包含分离文件里残留的前奏/伴奏，不把自动裁边称为人声边界真值。

超出设备35音音域的窗口在结果说明中明确列出，原音高CSV/MIDI和试听全部保留，没有削去低音/钳位来伪造可上传结果。四首曲目的音准和听感仍需试听，未把本轮两个位置的改善说成四首全曲已通过人工验收。

## 验证与限制

{release['android_test_count']}项Android单元测试、构建、Lint通过；34个原PCM窗口重新运行实际App，阶段链与最终事件完全一致。7组上传ACK/CRC/原子RAM/自动播放RTL仿真通过；6组单乐器隔离结果与0.8相同。每个窗口的发声时间并集不变，真实静音未被填满。新增测试覆盖半音移调、绝对时间平移、稳定140ms真音、真间隔、独立辅音/起音、正常宽颤音和缺测。

这些新规则属于“表达性人声主音投影”，没有篡改F0或声称测量到了原声中不存在的稳定平台。较短的不规则偏调同音重复、故意只唱半个宽颤音，可能与阶进/滑入假设不可区分，仍可能被错误规整；这类录音应在音符编辑中撤销/修正。不能保证任意录音的表演意图都可唯一恢复。

APK版本0.9，算法版本7；覆盖安装后对旧录音点“重新识别”才应用新算法。手机麦克风、蓝牙、OLED及FPGA实物声音/延迟本轮未测；没有烧录。
'''
(O/'本轮说明.md').write_text(report,encoding='utf8')
(O/'试听清单.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf8')
code=O/'源码与验证';code.mkdir(exist_ok=True)
for p in [*list((R/'app/android/app/src/main/java/cn/soundcore/instrument').glob('*.kt')),*list((R/'app/android/app/src/test/java/cn/soundcore/instrument').glob('*.kt')),
 R/'app/android/app/build.gradle.kts',*[R/f'scripts/{x}' for x in ['recompute_vocal_contours.py','verify_vocal_contours.py','package_vocal_contours.py']],
 *[R/f'scripts/support/{x}.java' for x in ['CheckGenericVocal','CheckVocalAudio','DumpVocalContourStages']]]:
 q=code/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
for p in ['release.json','source_audio_sha256.json','audio_class_sha256.json','baseline_sha256.json','changes.diff','regression_checks.json','all_contour_changes.json','instrument_isolation.json','gradle.log','verify.log','apk_certificate.log','audio_results.json']:
 shutil.copy2(B/p,code/p)
for d in (B/'audio').glob('*/*'):
 for p in d.glob('*.csv'):
  q=code/'audio_evidence'/d.relative_to(B/'audio')/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
hashes={p.relative_to(O).as_posix():sha(p) for p in O.rglob('*') if p.is_file() and p.suffix.lower()!='.zip' and p.name!='SHA256.json'}
(O/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
z=O/'四曲算法结果_v0.9_试听与源码.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6) as f:
 for p in O.rglob('*'):
  if p.is_file() and p!=z:f.write(p,p.relative_to(O))
with zipfile.ZipFile(z) as f:assert f.testzip() is None
print('Packaged',len(inventory),'MP3s;',len(hashes),'hashed files; zip',round(z.stat().st_size/1024**2,2),'MiB',flush=True)
