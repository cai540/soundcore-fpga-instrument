"""Package the real 0.8 output, preserving accepted phrases and known limits."""
from pathlib import Path
import json,hashlib,shutil,csv,subprocess,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_phrase_20261029';OUT=ROOT/'output/vocal_phrase_20261029'
OLD=ROOT/'build/vocal_natural_20261029/audio'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((B/'release.json').read_text(encoding='utf8'));assert release['android_test_count']>=182
assert len(release['endpoint_checks'])==7
for p,h in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():assert sha(ROOT/p)==h,p
OUT.mkdir(exist_ok=True);apk=OUT/'声芯_通用人声识谱_v0.8.apk'
shutil.copy2(release['apk_source'],apk);assert sha(apk)==release['apk_sha256']
def notes(p):
 return [dict(s=int(x['start_ms']),e=int(x['start_ms'])+int(x['duration_ms']),n=int(x['midi'])) for x in csv.DictReader(p.open(encoding='utf8'))]
def mp3(x,p):
 subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar','16000','-ac',str(1 if x.ndim==1 else 2),'-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(p)],input=x.astype('<i2').tobytes(),check=True)
def render(ns,begin,end):
 size=(end-begin)*16;out=np.zeros(size,dtype='<i2');phase=0.
 for n in ns:
  s=max(begin,n['s']);e=min(end,n['e'])
  if e<=s:continue
  a=(s-begin)*16;count=(e-s)*16;t=np.arange(count)
  env=np.minimum(1,np.minimum(t/(16000*.012),(count-1-t)/(16000*.018))).clip(0)
  w=2*np.pi*440*2**((n['n']-69)/12)/16000
  out[a:a+count]=(np.sin(phase+w*t)*env*7500).astype('<i2');phase=(phase+w*count)%(2*np.pi)
 return out
# The earlier preview ended at source 87.09, inside the last held lyric.
# This six-second view uses an EXISTING full-context 40s result, not a 46s
# recognition or an invented continuation beyond the App's advertised limit.
tail=B/'audio/zuguo/chunk_02';tail_old=OLD/'zuguo/chunk_02'
newtail=render(notes(tail/'notes.csv'),3400,9400);oldtail=render(notes(tail_old/'notes.csv'),3400,9400)
folder=OUT/'我和我的祖国';folder.mkdir(exist_ok=True)
mp3(newtail,folder/'我和我的祖国_完整尾句_6秒.mp3')
mp3(np.column_stack([oldtail,newtail]),folder/'我和我的祖国_完整尾句_旧左新右_6秒.mp3')
queries=json.loads((B/'offline_word_queries.json').read_text(encoding='utf8'))
names={('一',64.18),('每',69.14),('山',71.66),('袅',78.36),('袅',78.82),('上',84.61),('一',84.91),('道',85.66),('辙',85.87)}
word_rows=[]
for q in queries:
 if (q['char'],q['begin']) not in names:continue
 window='chunk_02' if q['char']=='辙' else 'first40';offset=80000 if window=='chunk_02' else 47090
 row=dict(char=q['char'],source_begin=q['begin'],source_end=q['end'],window=window,reference=[n['source_midi'] for n in q['reference']])
 for v,d in [('old',OLD/'zuguo'/window),('new',B/'audio/zuguo'/window)]:
  row[v]=[dict(begin=(n['s']+offset)/1000,end=(n['e']+offset)/1000,midi=n['n']) for n in notes(d/'notes.csv') if min(n['e']+offset,q['end']*1000)-max(n['s']+offset,q['begin']*1000)>=40]
 word_rows.append(row)
(OUT/'本次标记位置.json').write_text(json.dumps(word_rows,ensure_ascii=False,indent=2),encoding='utf8')
metric=json.loads((B/'comparison_metrics.json').read_text(encoding='utf8'));quality=json.loads((B/'quality_metrics.json').read_text(encoding='utf8'))
aggregate={}
for name in ['zuguo','chilege']:
 full=[r for r in metric if r['name']==name and r['window'].startswith('chunk_')];aggregate[name]={}
 for v in ['old','new']:
  frame=sum(x['reference_distance'][v]['reference_interior_frames'] for x in full);match=sum(x['reference_distance'][v]['same_pitch_frames'] for x in full)
  aggregate[name][v]=dict(frames=frame,matching=match,agreement=match/frame,notes=sum(x['reference_distance'][v]['notes'] for x in full))
first=next(x['reference_distance'] for x in metric if x['name']=='zuguo' and x['window']=='first40')
plt.rcParams['font.sans-serif']=['SimHei'];plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(4,1,figsize=(13,10),layout='constrained')
for ax,(begin,end,title) in zip(axs,[(63.6,65.1,'一首赞歌：失锁八度复核'),(68.8,70.3,'每一座：恢复被吞的换音'),(71.6,72.9,'高山：弱释放尾不再另敲一个键'),(78.25,79.5,'袅袅：仍保留不确定音高，未按曲谱写死')]):
 d=B/'audio/zuguo/first40';tr=np.genfromtxt(d/'vocal_frontend.csv',delimiter=',',names=True)
 ax.plot(tr['ms']/1000+47.09,tr['pitch'],color='#9ba4b4',alpha=.75,lw=1,label='声学F0估计')
 for path,color,label in [(OLD/'zuguo/first40/notes.csv','#547cbc','0.7'),(d/'notes.csv','#c77c27','0.8')]:
  ns=[n for n in notes(path) if n['e']/1000+47.09>begin and n['s']/1000+47.09<end]
  for i,n in enumerate(ns):
   ax.plot([max(begin,n['s']/1000+47.09),min(end,n['e']/1000+47.09)],[n['n']]*2,color=color,lw=2.5,label=label if i==0 else None)
   ax.plot(max(begin,n['s']/1000+47.09),n['n'],marker='|',color=color,ms=10)
 raw=tr['pitch'][(tr['ms']/1000+47.09>=begin)&(tr['ms']/1000+47.09<=end)];raw=raw[np.isfinite(raw)]
 ns2=notes(d/'notes.csv');ys=[n['n'] for n in ns2 if n['e']/1000+47.09>begin and n['s']/1000+47.09<end]
 ax.set_ylim(min([float(raw.min()),*ys])-.5,max([float(raw.max()),*ys])+.5)
 ax.set_title(title);ax.set_xlim(begin,end);ax.set_ylabel('MIDI音高');ax.grid(alpha=.2);ax.legend(ncol=3,loc='upper right')
axs[-1].set_xlabel('原始人声文件时间 / 秒');fig.savefig(OUT/'本轮位置对照.png',dpi=135);plt.close(fig)
report=f'''# 通用人声识谱0.8：本轮实际改动与试听

本轮修改通用算法，不用歌曲名称、歌词时间、固定调号、MIDI模板或文件指纹决定音符。原有精修曲库和FPGA固件不变，本轮未烧录。以下歌词只作离线定位；所有输出来自最终App代码的原始PCM复算。

## 已修正与保留

- **“一首赞歌”的“一”**：复核已有同音再起音处的pYIN候选，不让先前低音路径长期锁住新八度。只有上八度候选持续占优、奇偶谐波结构改变且没有可靠低音共周期证据时，才恢复更高的主旋律。真实低音即使偶次谐波很强，也会由共同相位锁定保护；缺基频还检查3/5/7次奇次族。
- **“每一座高山”的“每”**：原解码对快速变化帧减权，把本来存在的70与后一69合并。现在使用不减该权重的备选解码只提出旧长音内部切口，保持已接受音符的端点；新切口仍需原始测量、明确声学边界及稳定核/直接观测的完整峰谷结构。不全局调低平滑、不重写前两句。
- **“高山”的“山”**：原F0确有微弱上弯，错误在于把衰减的释放尾另变成一次强62起音。联合衰减、弱起音、低有声质量和缺少稳定音核，将其留在60主音内，保留末端时刻。清楚的140/150ms真平台、弱而稳定的真尾、颤音中心、真实静音都有保护。
- **前两句**：最终事件的音高、起点和时长与0.7逐项一致，包括最后已认可的长音。
- **“袅袅”和“上”**：尚未可靠自动修正。第二“袅”的实测中心约76.6，可能是76的偏高演唱，也可能是77的偏低演唱；“上”在63–65间有连续变化，频谱没有证实稳定62。为它们加入邻音顺滑先验，会把同样声学观测的真实偏调重复音也改错，因此本轮没有硬改。第一“袅”及“上一道”的“一”也保留原结果。
- **“辙”**：完整数据音高65稳定，上一份首40秒试听在源时间87.09截止，切到了尾字中间。新增“完整尾句6秒”取自有完整上下文的40秒窗口，不伪造超40秒的识别结果。该词不是全曲自动截短。

“每”的新70仍从原事件69.24开始，比旧人工词头69.14晚约100ms；未把人工词界当作可以硬写入算法的答案。其余不能确定的转音、弱尾与音节边界也没有宣称已全部解决。

## 组合验证

{release['android_test_count']}项Android测试、构建和Lint通过；21个原样PCM窗口运行实际App编译类，阶段重建与最终识别事件一致；7个可上传片段完成ACK/CRC/原子RAM/播放RTL回放。6组单音乐器结果与0.7保持一致。两段前句测试和四个儿歌片段逐事件保留。手机、蓝牙和FPGA实物听感/延迟未在本轮实测。

祖国首40秒对旧精修稳定区同音高由{first['old']['same_pitch_frames']}/{first['old']['reference_interior_frames']}（{first['old']['pitch_agreement']:.2%}）变为{first['new']['same_pitch_frames']}/{first['new']['reference_interior_frames']}（{first['new']['pitch_agreement']:.2%}）。完整分窗从{aggregate['zuguo']['old']['matching']}/{aggregate['zuguo']['old']['frames']}变为{aggregate['zuguo']['new']['matching']}/{aggregate['zuguo']['new']['frames']}；敕勒从{aggregate['chilege']['old']['matching']}/{aggregate['chilege']['old']['frames']}变为{aggregate['chilege']['new']['matching']}/{aggregate['chilege']['new']['frames']}。这是与旧编排的距离，不是独立真值准确率；短音和边界另有专门检查，不能只看此比例。

## 原理与不可辨边界

八度复核不是“第二谐波强就升八度”。先从宽带2f0解析信号恢复共同相位，再把原PCM按它去调频，低通提取1/3/5/7族；检查整数共周期相位关系的幅度加权单位相位平方。这样既消除共同宽颤音，也保留相位半角的符号歧义。独立Kotlin/Python复核36组缺基频+宽共振音全部受保护，真实目标两份重叠窗口仍解锁，数值误差小于3e-13。

强时变声道相对相位、多个声源、以及有意偏调且衰减的不规则尾音，仍可能与错误或释放弯曲具有相似观测。新模块是有约束的旋律推断，不是对所有录音意图的数学证明。已知反例均保留在evidence，不用曲目特例绕开。

## 使用和文件

覆盖安装本APK后选择原片段“重新识别”；旧缓存不会自动改写。首40秒和左右声道A/B保持相同源时钟；“完整尾句6秒”查看末句。试听使用统一参考合成音色，比较音高和节奏，不是FPGA真实口琴录音。全文件诊断由独立40秒窗口拼接，不能当成一次完整长曲识别。

功能上限未改：导入≤180秒、单次识别/上传≤40秒、35音/512事件。兰亭序first40和敕勒源chunk06的超音域失败仍保留，未删最低音伪造成功。source是最终App源和测试；evidence保存实际事件、哈希、端点与独立审查；SHA256.json核对发布内容。
复算脚本需要本工程缓存、开发环境和原录音；压缩包没有复制全部原始音频，也不将环境相关脚本称为无依赖独立安装工具。
'''
(OUT/'本轮说明.md').write_text(report,encoding='utf8');(ROOT/'docs/vocal_phrase_2026-10-29.md').write_text(report,encoding='utf8')
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for p in B.glob('*.json'):shutil.copy2(p,evidence/p.name)
for name in ['android_verified.log','apk_certificate.log','verification.log','audio_batch.log','changes.diff','summary.log']:
 shutil.copy2(B/name,evidence/name)
for dirname in ['pitch','segmentation','audit']:
 for p in (B/dirname).glob('*'):
  if p.is_file() and p.suffix in ['.json','.md','.log','.py','.kt','.png']:
   d=evidence/dirname/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 d=evidence/'unit_tests'/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
results=json.loads((B/'audio_results.json').read_text(encoding='utf8'))
for item in results:
 d=Path(item['new']);target=evidence/'actual_scores'/item['name']/item['window'];target.mkdir(parents=True,exist_ok=True)
 for p in d.glob('*'):
  if p.is_file() and (p.suffix in ['.csv','.json'] or p.name in ['endpoint.log','android_upload.hex','android_upload_meta.vh','events.mem']):
   if (p.name.startswith('android_') or p.name in ['endpoint.log','events.mem']) and not item.get('wire_fixture'):continue
   shutil.copy2(p,target/p.name)
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():
  d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
for p in [ROOT/'app/android/app/build.gradle.kts',*[ROOT/'scripts'/n for n in ['compare_vocal_phrase.py','summarize_vocal_phrase.py','evaluate_vocal_phrase.py','verify_vocal_phrase.py','package_vocal_phrase.py']],*[ROOT/'scripts/support'/n for n in ['CheckGenericVocal.java','CheckVocalAudio.java','DumpVocalPhraseStages.java','CheckInstrumentIsolation.java']]]:
 d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
media=[]
for p in OUT.rglob('*.mp3'):
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=channels,sample_rate','-of','json',str(p)],text=True,encoding='utf8'))
 expected=2 if '左_' in p.name or '旧左新右' in p.name else 1;assert info['streams'][0]['channels']==expected,str(p)
 assert float(info['format']['duration'])>0;media.append({'file':p.relative_to(OUT).as_posix(),**info})
(evidence/'media_checks.json').write_text(json.dumps(media,ensure_ascii=False,indent=2),encoding='utf8')
release.update(apk=str(apk),aggregate_offline_comparison=aggregate,status='software_verified_physical_listening_pending',accepted_first_two_lines_preserved=True)
(B/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8');(evidence/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files};(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'通用人声识谱_0.8_源码试听与验证.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p,h in manifest.items():assert hashlib.sha256(z.read(p)).hexdigest()==h,p
print(json.dumps({'apk':str(apk),'apk_sha256':sha(apk),'files':len(files),'previews':len(media),'aggregate':aggregate},ensure_ascii=False,indent=2))
