"""Package the measured 0.6 candidate with concrete successes AND counterexamples."""
from pathlib import Path
import json,shutil,hashlib,csv,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_refine_20261029';OUT=ROOT/'output/vocal_refine_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((B/'release.json').read_text(encoding='utf8'))
assert release['android_test_count']==94 and len(release['endpoint_checks'])==7
old=json.loads((B/'baseline/build/vocal_syllable_20261029/release.json').read_text(encoding='utf8'))
assert sha(Path(old['apk']))==old['apk_sha256'],'Published 0.5 changed'
for p,h in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():assert sha(ROOT/p)==h,p
OUT.mkdir(exist_ok=True)
apk=OUT/'声芯_通用人声识谱_v0.6_候选.apk';shutil.copy2(release['apk_source'],apk);assert sha(apk)==release['apk_sha256']
release['apk']=str(apk);release['previous_05_apk_preserved']=str(old['apk'])
release['status']='candidate_listening_and_generalization_pending'
release['neural_model_integrated']=False
metrics=json.loads((B/'comparison_metrics.json').read_text(encoding='utf8'));aggregate={}
for name in ['zuguo','chilege']:
 groups=[x['reference_distance'] for x in metrics if x['name']==name and x['window'].startswith('chunk_')]
 aggregate[name]={}
 for version in ['old','new']:
  n=sum(x[version]['reference_interior_frames'] for x in groups);p=sum(x[version]['same_pitch_frames'] for x in groups)
  aggregate[name][version]={'reference_interior_frames':n,'same_pitch_frames':p,'agreement':p/n,
   'notes':sum(x[version]['notes'] for x in groups),'sub200ms_notes':sum(x[version]['sub200ms_notes'] for x in groups)}
release['aggregate_reference_distance']=aggregate
release['incompatible_windows']=[{'name':x['name'],'window':x['window'],'reason':x['device_error'],'low':x['low_midi'],'high':x['high_midi']}
 for x in json.loads((B/'audio_results.json').read_text(encoding='utf8')) if x.get('device_error')]

def notes(path):
 return [{'s':int(x['start_ms'])/1000,'e':(int(x['start_ms'])+int(x['duration_ms']))/1000,'midi':int(x['midi'])}
  for x in csv.DictReader(path.open(encoding='utf8'))]
plt.rcParams['font.sans-serif']=['SimHei'];plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(4,1,figsize=(13,10),constrained_layout=True)
examples=[('chilege','chunk_02',1.5,3.5,'敕勒歌·盏：长音内的转音'),
 ('chilege','chunk_02',29.5,32.,'敕勒歌·茫：连续下滑被切成台阶'),
 ('chilege','chunk_03',31.8,35.4,'敕勒歌·川：错低八度'),
 ('zuguo','first40',36.2,37.7,'我和我的祖国·路：滑入已改善，尾滑仍保留')]
for ax,(name,window,start,end,title) in zip(axes,examples):
 for path,color,label in [(ROOT/f'build/vocal_syllable_20261029/audio/{name}/{window}/notes.csv','#527cbc','0.5'),
  (B/f'audio/{name}/{window}/notes.csv','#ce7d24','0.6候选')]:
  selected=[x for x in notes(path) if x['e']>start and x['s']<end]
  for i,n in enumerate(selected):
   ax.plot([max(start,n['s']),min(end,n['e'])],[n['midi']]*2,color=color,lw=2,label=label if i==0 else None)
   ax.plot(max(start,n['s']),n['midi'],marker='|',color=color,ms=10)
 ax.set_title(title);ax.set_xlim(start,end);ax.set_ylabel('MIDI音高');ax.grid(alpha=.2);ax.legend()
axes[-1].set_xlabel('当前40秒窗口内的相对时间 / 秒');fig.savefig(OUT/'具体位置前后对照.png',dpi=135);plt.close(fig)

position=(B/'position_comparison.md').read_text(encoding='utf8')
rows=[]
for name,title in [('zuguo','我和我的祖国'),('chilege','敕勒歌')]:
 a=aggregate[name]['old'];b=aggregate[name]['new']
 rows.append(f"|{title}|{a['agreement']:.2%} → {b['agreement']:.2%}|{a['sub200ms_notes']} → {b['sub200ms_notes']}|{a['notes']} → {b['notes']}|")
report='''# 通用人声识谱0.6：具体根因与本轮结果

这是继续修正后的候选版，尚不能作为“全部音准和逐字分段均已验收”的正式版本。旧精修曲库/FPGA程序、0.5安装包均保留，本次没有扫描硬件、写SRAM或Flash。

## 定位出的共同原因

1. **转音没有稳定平台也会变成音符。** 0.5的150ms最短持续时间只限制状态长度，连续滑音仍可能被切成多个凑够时长的音符。现在检查候选附近连续稳定核心、轨迹跨度、回返形态；对严格单向的连续滑音簇整体重分配时间，保留两端主音。真实150ms快音、350ms半音及恒定下降音阶有保护测试。
2. **长元音音量起伏被误当再次起音。** 原来主要依靠能量谷。现在弱/宽能量谷还要有增益归一化的宽频谱包络变化证据；强且窄的清楚再次起音仍保留。羊长音的假起音可去除；下长音中另两处有真实气息中断，局部声学形态与辅音重起音重叠，尚不能全部自动分清。
3. **总有声概率被误当成选中音高的可靠性。** pYIN的总候选质量较高也可能选中低八度或低三倍频。现在用原PCM对基频/谐波栅格及半间距峰进行独立复核，结合多帧一致性和前后注册连续性，只在证据充分时纠正倍频。真实低音、缺弱基频但仍有奇次谐波、真实八度跳进均有测试。
4. **YIN差分漏减有限窗尾部能量。** 已补齐并通过直接时域差分数值测试；同音高bin的候选质量改为累加。这个数学修复主要校正概率标定，不能单独解决大部分听感错误。新公式仅启用人声路径，单音乐器的既有结果保留。

所有推断函数只输入PCM/音高轨迹/声学证据，不读歌曲名称、歌词、精修音序、MIDI模板或文件指纹。报告里的词和时间只用于离线诊断；运行时不会查这个表。无上传录音到云端的新依赖。

## 实际改善与反例

首40秒保持相同PCM、相同时间轴：祖国音符65→57、与精修稳定区同音高91.63%→92.19%；敕勒60→54、91.83%→92.39%。这些是对旧编排的距离，不是独立音准准确率。源时间标记有人工偏移，原声与编排也并不总是完全相同。

对完整文件按40秒窗口复算，结果如下。特意同时列出退步：祖国减少碎音，但稳定区音高吻合略降，不能宣称音准全面改善。

|完整文件分窗|相对精修稳定区同音高|短于200ms音符|全部音符|
|---|---:|---:|---:|
'''+ '\n'.join(rows)+'''

稳定区排除每个精修音首尾各150ms，缺声也计为不一致。短音不全是错误；不能单纯以音符变少宣传效果。后段来自相同歌手/录音，不是独立泛化集。

尚未解决：祖国首句相邻半音可能合并；“我/每”附近仍有半音偏差；路尾部下滑未被安全消除；敕勒下长音仍有气息引起的再次起音。原PCM与旧编排不一致时，不从参考硬写某一音或统一移调。

另做了一组独立离线神经F0对照，按上游时间戳和统一参数运行，未显示全面稳定优势，因此未加入APK，也没有引入新的模型运行库。原始对照和时间戳检查在evidence/neural中；它不作为本版改善的依据。

额外测试中，兰亭序首段出现有局部谱支持的短低41，音域跨度超过设备35音；敕勒源240秒以后的残余片段也超域。保留原始诊断，App按已有规则禁止该结果直接上传，没有为凑音域删低音或伪造端点成功。该输入仍需人工核对，不属于本轮已经解决的泛化案例。

## 验证与使用

- 94项Android单元测试、构建、Lint无Error/Fatal。
- 21个相同PCM窗口实际运行新App编译代码；7份可上传结果完成ACK/CRC/原子RAM/整曲播放的RTL回放。额外超域样本没有计作可播放成功。
- 6组单音乐器PCM与0.5输出逐项一致；4000组随机事件/真实静音不变量检查无越界、重叠、空结果或填入零RMS间隔。
- 谱起音13处Python/Kotlin误差<5e-13；数学差分与直接计算误差约1e-13。新处理可取消，音频/曲谱时钟保留。
- 真实手机收音、系统解码、无线、板载音色和最终听感没有在本轮实测；桌面耗时不能作手机或<5ms演奏延迟证明。

安装本包候选APK后，曲目→录一段，接着奏→人声/哼唱→重新识别原片段。旧保存结果不自动覆盖，局部重算仍含旧结果时继续提示。原有两首精修曲库不变。

听感核对建议先听敕勒歌“复核80至120秒”的旧版左/新版右，它包含盏、下和茫；再听两首首40秒。试听是相同参考合成音，用于比较音高、节奏和碎音，并非FPGA实物音色。

全文件试听由40秒窗口拼接，窗口边界可能截断音符，保留空白；它是诊断材料，不能当作新曲库直接烧录。App导入文件≤180秒，单次识别/上传≤40秒，设备仍是35音/512事件。

## 具体位置

'''+position.split('##',1)[0].replace('# 0.5与0.6的具体位置对照','')+'''

## 文件

具体位置前后对照.png / 具体位置对照.md与.json列出定位；evidence含代码差异、测试XML、实际端点数据/日志、声学诊断、独立审查和全部指标；source含本版App源代码。SHA256.json覆盖发布内容。
'''
(OUT/'说明与具体问题.md').write_text(report,encoding='utf8');(ROOT/'docs/vocal_refine_2026-10-29.md').write_text(report,encoding='utf8')
shutil.copy2(B/'position_comparison.md',OUT/'具体位置对照.md');shutil.copy2(B/'position_comparison.json',OUT/'具体位置对照.json')
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for p in B.glob('*.json'):shutil.copy2(p,evidence/p.name)
for name in ['android_verified.log','apk_certificate.log','verification.log','audio_batch.log','changes.diff']:
 shutil.copy2(B/name,evidence/name)
for directory,names in {'audit':['audit.md','findings.md','selected_errors.json','onset_features.json','onset_kotlin_parity.json','independent_code_review.md','gate_fuzz_review.log','reviewed_production_sha256.json'],
 'pitch':['pitch_report.md','diagnostics.json','harmonic_kotlin_real_checks.json','harmonic_kotlin_tests.log'],
 'segmentation':['README.md','kotlin_metrics.json','tests.log'],
 'neural':['report.md','neural_report.md','swift_results.json','timestamp_check.json']}.items():
 for name in names:
  p=B/directory/name
  if p.exists():
   d=evidence/directory/name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 d=evidence/'unit_tests'/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
for item in json.loads((B/'audio_results.json').read_text(encoding='utf8')):
 d=Path(item['new']);target=evidence/'actual_scores'/item['name']/item['window'];target.mkdir(parents=True,exist_ok=True)
 for name in ['notes.csv','result.json','frontend.log','android_score.json','android_upload.hex','android_upload_meta.vh','endpoint.log','events.mem']:
  if name.startswith('android_') or name in ['endpoint.log','events.mem']:
   if not item.get('wire_fixture'):continue
  if (d/name).exists():shutil.copy2(d/name,target/name)
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():
  d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
scripts=['compare_vocal_refine.py','summarize_vocal_refine.py','verify_vocal_refine.py','report_vocal_refine_positions.py','package_vocal_refine.py']
for p in [ROOT/'app/android/app/build.gradle.kts',*[ROOT/'scripts'/n for n in scripts],
 *[ROOT/'scripts/support'/n for n in ['CheckGenericVocal.java','CheckVocalAudio.java','CheckInstrumentIsolation.java','DumpVocalFrontEnd.java']]]:
 d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
(B/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
(evidence/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files};(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'通用人声识谱_0.6_对照与验证包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p,h in manifest.items():assert hashlib.sha256(z.read(p)).hexdigest()==h,p
print(json.dumps({'apk':str(apk),'sha256':sha(apk),'files':len(files),'aggregate':aggregate,'unplayable_windows':release['incompatible_windows']},ensure_ascii=False,indent=2))
