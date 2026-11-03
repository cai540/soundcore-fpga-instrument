"""Publish verified App + same-clock listening comparisons, preserving 0.4."""
from pathlib import Path
import json,shutil,hashlib,zipfile,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_syllable_20261029';OUT=ROOT/'output/vocal_main_notes_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((B/'release.json').read_text(encoding='utf8'))
assert release['android_test_count']==68 and len(release['endpoint_checks'])==8
for p,h in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():assert sha(ROOT/p)==h
apk=OUT/'声芯_录音主音优化_v0.5.apk';shutil.copy2(release['apk_source'],apk);assert sha(apk)==release['apk_sha256']
release['apk']=str(apk)
metrics=json.loads((B/'comparison_metrics.json').read_text(encoding='utf8'))
rows={m['name']:m for m in metrics if m['window']=='first40'}
aggregate={}
for name in ['zuguo','chilege']:
 group=[m['reference_distance'] for m in metrics if m['name']==name and m['window'].startswith('chunk_')]
 aggregate[name]={}
 for version in ['old','new']:
  count=sum(g[version]['reference_interior_frames'] for g in group)
  agree=sum(g[version]['same_pitch_frames'] for g in group)
  aggregate[name][version]={'reference_interior_frames':count,'same_pitch_frames':agree,'pitch_agreement':agree/count if count else None,
   'sub200ms_notes':sum(g[version]['sub200ms_notes'] for g in group),'notes':sum(g[version]['notes'] for g in group)}
release['full_window_reference_distance']=aggregate
(B/'aggregate_reference.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2),encoding='utf8')

plt.rcParams['font.sans-serif']=['SimHei'];plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(2,1,figsize=(15,7),constrained_layout=True)
for ax,name,title in zip(axes,['zuguo','chilege'],['我和我的祖国','敕勒歌']):
 reference=json.loads((B/name/'reference.json').read_text(encoding='utf8'))
 for k,n in enumerate(reference['references']):
  if n['start']<12000 and n['end']>0:ax.plot(np.array([max(0,n['start']),min(12000,n['end'])])/1000,[n['midi']]*2,
   color='0.55',lw=6,alpha=.35,label='旧精修参考（源时间）' if k==0 else None)
 for path,color,label in [(ROOT/f'build/generic_four_vocals_20261028/{name}/first40/notes.csv','#537dbc','旧通用算法'),
  (B/f'audio/{name}/first40/notes.csv','#cf7c22','新版主音算法')]:
  for i,n in enumerate(csv.DictReader(path.open(encoding='utf8'))):
   s=int(n['start_ms']);e=s+int(n['duration_ms'])
   if s<12000:ax.plot(np.array([s,min(12000,e)])/1000,[int(n['midi'])]*2,color=color,lw=1.7,label=label if i==0 else None)
 ax.set_title(title+'：首段前12秒，保留真实时长与空白');ax.set_xlim(0,12);ax.set_ylabel('MIDI音高');ax.grid(alpha=.2);ax.legend(loc='lower right')
axes[-1].set_xlabel('相对所选片段的时间 / 秒');fig.savefig(OUT/'同时间轴主音对照.png',dpi=140);plt.close(fig)

table=[]
for name,title in [('zuguo','我和我的祖国'),('chilege','敕勒歌')]:
 m=rows[name]['reference_distance'];a=m['old'];b=m['new']
 table.append(f"|{title}|{a['notes']} → {b['notes']}|{a['sub200ms_notes']} → {b['sub200ms_notes']}|{a['pitch_agreement']:.1%} → {b['pitch_agreement']:.1%}|")
report='''# 人声录音识谱：稳定主音优化 0.5

已修改通用人声算法，并编译进入APK。原有《我和我的祖国》《敕勒歌》精修曲库、FPGA固件及接线保持原样；没有烧录。

## 原因与修改

逐帧音高先四舍五入再切音，会把颤音跨过半音边界、滑音经过中间音高、短时低八度误检当成新音。仅根据音量下降再次起音，则会把长音中的颤动切碎。原来同音间≤120ms的空白还可能被直接填上，吞掉真正的呼吸。

现在人声分支在量化前减弱有连续运动证据的3–9Hz周期颤音；用双侧证据修复短时、低置信的八度误检；用带最短持续时间的状态解码提取稳定主音。空白仅在仍有明确声能时桥接，真实静音保留。同音再次起音使用能量谷的显著度、宽度、间隔和周期性共同判断，避免只靠一个音量阈值。

不是简单把所有短音删除：真正150ms连续主音、350ms半音变化、高置信八度跳进、同音再次起音与短呼吸都有回归案例。单音乐器走原分支；6组相同PCM在0.4和0.5输出逐项一致。

## 与旧精修结果对照

精修结果只在离线核对中读取。运行时仅输入PCM、输入类型及取消/进度回调，不读取曲名、歌词、曲谱、文件指纹或旧MIDI。两首40秒与0.4使用逐样本相同的分析PCM。

旧编排对演奏时长做过人工伸缩。这里改用其source_start_s/source_end_s/source_midi与原人声对照，避免把编排时间误当作原唱节奏；《敕勒歌》比较时也移除了旧播放的整体高八度。

|同一40秒片段|总音符数|短于200ms音符|参考稳定区同音高比例|
|---|---:|---:|---:|
'''+ '\n'.join(table)+'''

稳定区剔除每个精修音首尾各150ms；漏掉的稳定区按不一致计入，没有靠删除难音提高分数。以上是“与旧人工编排的距离”，不是独立音准准确率。人工源时间标记存在偏差，200ms短音也不全是错误，不能仅凭音符数判断好坏。

主要改善在《我和我的祖国》的碎音与短时错八度。《敕勒歌》的音高改善较小，部分弱声、尾音和字内合并/重复起音仍不理想。包括《我和我的祖国》首段相邻的半音主音仍可能合并，不能宣称已经达到精修曲谱的逐字质量。

## 验证范围

- Android 68项JUnit、APK构建和Lint检查通过（无Error/Fatal）。
- 21个人声窗口重新运行实际App编译类：四首原始人声首段、两首目标歌曲的13个完整文件窗口、4个儿歌/后段复核片段。
- 8份实际App生成的曲谱数据，完成ACK/CRC、原子写入RAM和全曲自动演奏的RTL端点回放。它不是蓝牙或实板实测。
- 6组单音乐器输入与0.4结果一致；旧APK、旧固件、精修曲谱与硬件源文件哈希保持。
- 保留120–160秒后段对照；未按该段逐音改写结果。开发中检查过两首首40秒，后段也来自同一歌手/同一源文件，不构成独立泛化数据集。

儿歌回归曾发现“压颤音导致同音重复丢失”，已加入宽辅音谷及重复起音保护。最终儿歌与保留段仍有个别误分，数量相近也不等于逐音正确，因此保留原声对照文件供听审，不报告100%识别率。

## 使用与试听

覆盖安装本包APK。在“曲目 → 录一段，接着奏”选择人声/哼唱，再重新识别原片段。已保存的旧结果会保留，不会被伪装成新版；只重算局部后仍含旧结果时会继续提示。未保存的原音需重新导入。

每首提供：新版、旧版左/新版右、人声左/新版右，以及旧精修在原时间轴的参考。所有试听保持真实时间与空白，采用相同参考音；主要用于听音高、节奏和起音，不能代表FPGA口琴/二胡的实物音色。MIDI为设备音域适配后的整段移调版本，CSV和原调试听保留提取音高。

全文件试听是40秒窗口拼接，边界可能切开音符，末尾静音保留；它是诊断材料，不替换板内149秒《敕勒歌》等精修作品。App单次仍识别/上传≤40秒，文件导入仍≤180秒。

手机真实收音、Android系统解码与界面、无线传输、板载扬声器及实际听感仍待验收。本次没有扫描硬件、写SRAM或写Flash。

## 可复核文件

对照统计.json、evidence/aggregate_reference.json、audio_results.json保留统计；changes.diff、Android日志、单元测试XML、8份端点日志和源代码可核对实现。SHA256.json覆盖交付内容。
'''
(OUT/'说明与对照结果.md').write_text(report,encoding='utf8')
(ROOT/'docs/vocal_main_notes_2026-10-29.md').write_text(report,encoding='utf8')
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for p in B.glob('*.json'):shutil.copy2(p,evidence/p.name)
for name in ['android_verified.log','apk_certificate.log','verification.log','audio_batch.log','changes.diff']:
 shutil.copy2(B/name,evidence/name)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 d=evidence/'unit_tests'/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
for item in json.loads((B/'audio_results.json').read_text(encoding='utf8')):
 if not item.get('wire_fixture'):continue
 d=Path(item['new']);target=evidence/'actual_scores'/item['name'];target.mkdir(parents=True,exist_ok=True)
 for name in ['notes.csv','result.json','android_score.json','android_upload.hex','android_upload_meta.vh','endpoint.log','tb_endpoint.v','events.mem']:
  shutil.copy2(d/name,target/name)
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():
  d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
for p in [ROOT/'app/android/app/build.gradle.kts',*[ROOT/'scripts'/n for n in
 ['compare_vocal_main_notes.py','summarize_vocal_main_notes.py','verify_vocal_main_notes.py','package_vocal_main_notes.py']],
 *[ROOT/'scripts/support'/n for n in ['CheckGenericVocal.java','CheckVocalAudio.java','CheckInstrumentIsolation.java']]]:
 d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
(B/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
(evidence/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'人声主音优化_0.5_试听与验证包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p,h in manifest.items():assert hashlib.sha256(z.read(p)).hexdigest()==h,p
print(json.dumps({'apk':str(apk),'sha256':sha(apk),'package':str(archive),'files':len(files),'aggregate':aggregate},ensure_ascii=False,indent=2))
