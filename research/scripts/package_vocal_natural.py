"""Package exact measured App output, preservation audits and source-clock previews."""
from pathlib import Path
import json,shutil,hashlib,csv,zipfile,subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_natural_20261029';OUT=ROOT/'output/vocal_natural_20261029'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((B/'release.json').read_text(encoding='utf8'))
assert release['android_test_count']>=143 and len(release['endpoint_checks'])==7
for p,h in json.loads((B/'audio_class_sha256.json').read_text(encoding='utf8')).items():assert sha(ROOT/p)==h,p
OUT.mkdir(exist_ok=True)
apk=OUT/'声芯_通用人声识谱_v0.7.apk';shutil.copy2(release['apk_source'],apk);assert sha(apk)==release['apk_sha256']
release.update(apk=str(apk),status='software_verified_listening_and_physical_acceptance_pending')
metrics=json.loads((B/'comparison_metrics.json').read_text(encoding='utf8'))
quality=json.loads((B/'quality_metrics.json').read_text(encoding='utf8'))
aggregate={}
for name in ['zuguo','chilege']:
 groups=[x['reference_distance'] for x in metrics if x['name']==name and x['window'].startswith('chunk_')]
 q=[x for x in quality if x['name']==name and x['window'].startswith('chunk_')]
 aggregate[name]={}
 for version in ['old','new']:
  frames=sum(x[version]['reference_interior_frames'] for x in groups);match=sum(x[version]['same_pitch_frames'] for x in groups)
  changes=[x for r in q for x in r['trusted_changes']];longs=[x for r in q for x in r['long_single_pitch']]
  aggregate[name][version]={'reference_interior_frames':frames,'same_pitch_frames':match,'agreement':match/frames,
   'notes':sum(x[version]['notes'] for x in groups),'sub200ms_notes':sum(x[version]['sub200ms_notes'] for x in groups),
   'trusted_changes_retained':sum(x[version]['retained'] for x in changes),'trusted_changes_total':len(changes),
   'extra_pitch_long_blocks':sum(len(x[version])>1 for x in longs),'long_blocks_total':len(longs)}
release['aggregate_offline_comparison']=aggregate
results=json.loads((B/'audio_results.json').read_text(encoding='utf8'))
release['incompatible_windows']=[{k:x[k] for k in ['name','window','low_midi','high_midi','device_error']} for x in results if x.get('device_error')]
release['stage_invariants']=json.loads((B/'stage_invariants.json').read_text(encoding='utf8'))
def notes(path):
 return [{'s':int(x['start_ms'])/1000,'e':(int(x['start_ms'])+int(x['duration_ms']))/1000,'midi':int(x['midi'])}
  for x in csv.DictReader(path.open(encoding='utf8'))]
plt.rcParams['font.sans-serif']=['SimHei'];plt.rcParams['axes.unicode_minus']=False
examples=[('zuguo','first40',1.3,2.8,47.09,'首句：恢复70→69，相邻半音不再整段合并'),
 ('zuguo','first40',27.6,29.2,47.09,'每一条河：保留180ms正常77短音'),
 ('zuguo','chunk_04',17.3,19.1,160,'最亲爱：恢复79→81→79，保留高音'),
 ('zuguo','first40',26.8,28.3,47.09,'残留：每字的含糊半音，尚未强行改写')]
fig,axes=plt.subplots(4,1,figsize=(13,10),layout='constrained')
for ax,(name,window,start,end,offset,title) in zip(axes,examples):
 d=B/'audio'/name/window
 track=np.genfromtxt(d/'vocal_frontend.csv',delimiter=',',names=True)
 ax.plot(track['ms']/1000+offset,track['pitch'],color='#909aab',alpha=.65,lw=1,label='声学估计F0')
 for path,color,label in [(ROOT/f'build/vocal_refine_20261029/audio/{name}/{window}/notes.csv','#527cbc','0.6'),
  (d/'notes.csv','#ce7d24','0.7')]:
  selected=[x for x in notes(path) if x['e']>start and x['s']<end]
  for i,n in enumerate(selected):
   ax.plot([max(start,n['s'])+offset,min(end,n['e'])+offset],[n['midi']]*2,color=color,lw=2.5,label=label if i==0 else None)
   ax.plot(max(start,n['s'])+offset,n['midi'],marker='|',color=color,ms=10)
 selected_raw=track['pitch'][(track['ms']>=start*1000)&(track['ms']<=end*1000)]
 selected_raw=selected_raw[np.isfinite(selected_raw)]
 ax.set_ylim(np.nanmin(selected_raw)-.5,np.nanmax(selected_raw)+.5)
 ax.set_title(title);ax.set_xlim(start+offset,end+offset);ax.set_ylabel('MIDI音高');ax.grid(alpha=.2);ax.legend(loc='upper right',ncol=3)
axes[-1].set_xlabel('原人声文件中的时间 / 秒');fig.savefig(OUT/'音高与正常换音对照.png',dpi=135);plt.close(fig)
rows=[]
for name,title in [('zuguo','我和我的祖国'),('chilege','敕勒歌')]:
 a=aggregate[name]['old'];b=aggregate[name]['new']
 rows.append(f"|{title}|{a['agreement']:.2%} → {b['agreement']:.2%}|{a['trusted_changes_retained']}/{a['trusted_changes_total']} → {b['trusted_changes_retained']}/{b['trusted_changes_total']}|{a['notes']} → {b['notes']}|{a['sub200ms_notes']} → {b['sub200ms_notes']}|")
report='''# 通用人声识谱0.7：保留正常换音，校正含糊音高

本版修改录音识谱的通用算法，没有为歌曲写旋律、歌词、调号、时间戳或文件指纹特例。旧精修曲谱只参与离线对照，不进入App识别函数。原有精修曲库和FPGA程序保持原样，本轮没有扫描或烧录硬件。

## 已完成的算法改动

1. **稳健种子后恢复真实换音。** 沿用0.6对滑音/碎音的过滤，再在每个长音内部检查原始测量是否支持不同主音，结合音色包络变化候选、时均音高和零均值颤音模型。恢复只发生在证据足够的区间，不整体降低平滑强度。每个旧音的端点、真实静音及既有边界保留。
2. **把宽颤音与主音中心分开。** 有声概率不再用来把颤音中心偏向更可靠的低谷；短音必须有真实测量支持，补点插值不能单独创造一个新音。过渡中的单向滑动不当成稳定主音。真实180ms快音可以恢复，不能用“短于200ms”一律删除。
3. **仅为含糊音高参考录音自身的调性。** 从整段录音估计多个调性候选，不预设歌曲调号；只允许含糊、缺乏稳定核的音在相邻半音内修正。稳定半音、清楚颤音、证据不足、RMS真静音和新恢复的可靠音优先保留。该调性先验使用已知Krumhansl/Kessler方法，并非声称其本身原创。
4. **修复缺测和边界程序错误。** 保留NaN所在原始时间，不再压缩时间导致颤音周期和稳定核误判；非10ms网格起点保持精确。可靠新增边界不会被之后的调性判断撤销；原来的同音重复和哪怕1ms的真实停顿也有保护。

曾试验直接降低转音惩罚、扩大整体重分段、放宽所有稳定平台门限，但会引入碎音或损害另一首曲子，因此没有加入生产版。最后还撤回了一条短周期放宽规则：独立反例证明，它会把单次平滑拱形弯音拆成新音。约98秒录音缺少足够的真实峰谷证据，所以没有为救回这一处而接受该风险。排除全部插值、只排除边缘插值等方案也损害过其他正常音，未加入生产版。相关候选及反例只作为evidence中的实验材料，不是App生产算法。

## 实际App代码复算

以下为完整文件按40秒分窗复算，对旧精修源时间轴的距离。稳定区排除每个参考音首尾各150ms；“正常换音”还要求两边原始F0时均中心均支持参考音。两种指标相互补充，不能把音符变少当作改善。

|文件|稳定区同音高|有声学支持的换音保留|全部音符|短于200ms音符|
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

祖国首40秒同音高由1641/1780（92.19%）提高至1671/1780（93.88%）；敕勒歌首40秒1481/1603保持不变。长参考主音内额外不同音高的块数，祖国8/52、敕勒6/79均未增加。这些并非独立人工标注的准确率，更不等于逐字转写正确率。

正常180ms短音得到恢复，短音数量可能略增，这是需要保留的旋律细节。四段两只老虎/小星星演示与后段保留录音的事件时间和音高逐项保持一致；后段来自相同录音，不能作为完全独立的泛化数据。

## 仍需明确的局限

祖国约97.94秒的“你”、161.91秒的“海”、180.61秒的“祖”和184.43秒的“是”仍有保守误合并；有些区间有效F0过少，有些不够区分真实短音与滑动。另发现边界补点可能影响子音统计，目前没有找到同时解决它且不损害其他正常音的方案，列为未解决，未按歌曲写补丁。“每”“和”附近还存在录音时均音高与旧精修参考不完全相同的情况，未按参考硬写音符。

强烈非周期转音、辅音/气息、伴奏残留，以及真实短音可能具有相近声学形态。本版改善了已定位的问题，但不能据此保证任何歌曲都达到手工精修听感。具体改善与未解决位置详见本目录“具体位置对照.md”和图。

## 验证和范围

- 143项Android单元测试通过，APK构建、Lint无Error/Fatal；同签名，可覆盖安装。
- 21段相同PCM由实际App编译类重算，四层阶段输出与真实识别最终事件逐字节一致，类哈希冻结。
- 7段适配设备音域的结果完成上传ACK、CRC、原子RAM和播放RTL回放；6组单音乐器结果逐项保持一致。
- 新处理有取消检查；真实静音、原始有声区间并集、同音重复、正常短音、新恢复音和半音/颤音均有反例测试及独立审查。
- 实际手机麦克风/系统解码、无线链路、FPGA最终音色和听感没有在本轮实测；桌面耗时不作为手机性能或小于5ms演奏延迟证明。

兰亭序首40秒及敕勒歌源文件240秒后的残余区间仍超出设备35音范围，保留诊断并按既有规则拒绝上传，没有删除最低音来伪造成功。该限制不会影响原有精修曲库。

## 安装与试听

安装声芯_通用人声识谱_v0.7.apk后，进入“曲目 → 录一段，接着奏 → 人声/哼唱”，选择原片段并重新识别。旧保存结果有版本提示，不会被静默覆盖；只重算局部时，旧区域仍保留原有标识。

先听“我和我的祖国_新版主音_40秒.mp3”。“旧版左_新版右”为相同原始时钟的左右声道A/B；“人声左_新版右”左声道人声、右声道识别主音。均使用相同参考正弦音色，比较旋律/音高/节奏，不是FPGA口琴或二胡实物录音。

“全文件分段复算”由多个40秒结果按源clock拼接，保留源空白且分窗边界可能截断音符，只是诊断材料。App仍是导入≤180秒、单次识别/上传≤40秒、设备35音/512事件，没有新增无限整曲识别能力。

evidence包含测试、实际事件、端点日志、音高轨迹和独立审查；source包含生产源码、测试和复算/核验脚本。SHA256.json用于核对包内容。
'''
(OUT/'说明与验证.md').write_text(report,encoding='utf8');(ROOT/'docs/vocal_natural_2026-10-29.md').write_text(report,encoding='utf8')
shutil.copy2(B/'pitch_release/release_audit.md',OUT/'具体位置对照.md')
shutil.copy2(B/'pitch_release/selected_cases.png',OUT/'改善与残留位置.png')
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for p in B.glob('*.json'):shutil.copy2(p,evidence/p.name)
for name in ['android_verified.log','apk_certificate.log','verification.log','audio_batch.log','changes.diff','summary.log']:
 shutil.copy2(B/name,evidence/name)
for dirname in ['pitch_release','model_review','review_release','onset']:
 for p in (B/dirname).glob('*'):
  if p.is_file() and p.suffix in ['.json','.md','.log','.py','.kt']:
   target=evidence/dirname/p.name;target.parent.mkdir(exist_ok=True);shutil.copy2(p,target)
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
 d=evidence/'unit_tests'/p.name;d.parent.mkdir(exist_ok=True);shutil.copy2(p,d)
for item in results:
 d=Path(item['new']);target=evidence/'actual_scores'/item['name']/item['window'];target.mkdir(parents=True,exist_ok=True)
 names=['notes.csv','result.json','vocal_frontend.csv','stage_seed.csv','stage_restored.csv','stage_quantized.csv','stage_final.csv',
  'run.log','frontend.log','android_score.json','android_upload.hex','android_upload_meta.vh','endpoint.log','events.mem']
 for name in names:
  if (name.startswith('android_') or name in ['endpoint.log','events.mem']) and not item.get('wire_fixture'):continue
  if (d/name).exists():shutil.copy2(d/name,target/name)
for p in (ROOT/'app/android/app/src').rglob('*'):
 if p.is_file():
  d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
scripts=['compare_vocal_natural.py','summarize_vocal_natural.py','verify_vocal_natural.py','evaluate_vocal_natural.py','package_vocal_natural.py']
for p in [ROOT/'app/android/app/build.gradle.kts',*[ROOT/'scripts'/n for n in scripts],
 *[ROOT/'scripts/support'/n for n in ['CheckGenericVocal.java','CheckVocalAudio.java','CheckInstrumentIsolation.java','DumpVocalFrontEnd.java']]]:
 d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
# Probe every published preview: channel count is part of each A/B label.
media=[]
for p in OUT.rglob('*.mp3'):
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=channels,sample_rate','-of','json',str(p)],text=True,encoding='utf8'))
 expected=2 if '左_' in p.name else 1;assert info['streams'][0]['channels']==expected,str(p)
 assert float(info['format']['duration'])>0
 media.append({'file':p.relative_to(OUT).as_posix(),**info})
(B/'media_checks.json').write_text(json.dumps(media,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(B/'media_checks.json',evidence/'media_checks.json')
(B/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
(evidence/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files};(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'通用人声识谱_0.7_源码试听与验证.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for p,h in manifest.items():assert hashlib.sha256(z.read(p)).hexdigest()==h,p
print(json.dumps({'apk':str(apk),'sha256':sha(apk),'files':len(files),'aggregate':aggregate,'unplayable':release['incompatible_windows']},ensure_ascii=False,indent=2))
