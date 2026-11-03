"""Independent score-prior audit. Never imported by App recognition.

Pitch references use the conventional nursery melodies. Boundaries below are
audio-assisted annotations, not professionally listened/verified ground truth.
This script reports that limitation with every metric.
"""
from pathlib import Path
import json,csv,hashlib,subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/melody_workbench_20261028/reference';OUT.mkdir(parents=True,exist_ok=True)
REF=ROOT/'examples/melody_reference';REF.mkdir(parents=True,exist_ok=True)
SOLFEGE={0:-5,1:0,2:2,3:4,4:5,5:7,6:9,7:11}
tune_t=[1,2,3,1,1,2,3,1,3,4,5,3,4,5,5,6,5,4,3,1,5,6,5,4,3,1,1,0,1,1,0,1]
tune_a=[1,1,5,5,6,6,5,4,4,3,3,2,2,1]
tune_b=[5,5,4,4,3,3,2,5,5,4,4,3,3,2]
# Monotonic onset anchors checked against energy/pitch spectra. The melody
# sequence is specified before and independently of evaluated note output.
t1=[150,600,1030,1430,1820,2290,2680,3170,3580,3960,4450,5300,5700,6150,
    7010,7180,7400,7630,7790,8280,8710,8900,9090,9330,9530,9960,10360,11000,11230,12130,12620,13000]
t2=[13860,14310,14680,15150,15530,16030,16380,16900,17250,17680,18160,19000,19400,19860,
    20730,20900,21120,21330,21590,21980,22420,22590,22800,23040,23230,23660,24080,24600,24990,25830,26340,26710]
w1=[470,970,1560,2010,2640,3170,3730,4850,5390,5970,6440,7080,7630,8230]
w2=[9280,9830,10470,10890,11570,12050,12730,13780,14360,14960,15500,16050,16520,17180]
w3=[18310,18750,19350,19810,20440,20950,21510,22620,23160,23740,24240,24880,25470,25920]
w4=[27090,27590,28210,28650,29270,29810,30380,31460,32020,32620,33100,33710,34260,34850]
items=[('tigers','两只老虎_30秒.mp3',63,tune_t*2,t1+t2,27310,13800),
       ('twinkle','小星星_35.8秒.mp3',61,tune_a+tune_b+tune_a+tune_a,w1+w2+w3+w4,35700,18300)]

results=[]
for key,filename,tonic,degrees,anchors,end,split in items:
 source=ROOT/'output/recording_demo_vocals_20261028'/filename
 audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4')
 frames=audio[:len(audio)//160*160].reshape(-1,160)
 rms=np.sqrt(np.mean(frames.astype(float)**2,axis=1))
 notes=[]
 for i,(degree,start) in enumerate(zip(degrees,anchors)):
  limit=anchors[i+1] if i+1<len(anchors) else end
  # Only release tails are derived acoustically; no recognized labels are used.
  stop=limit
  if limit-start>250:
   window=rms[max(0,(limit-140)//10):limit//10]
   if len(window) and window.min()<max(.002,rms[start//10:limit//10].max()*.08):
    quiet=np.flatnonzero(window<max(.002,rms[start//10:limit//10].max()*.08))
    if len(quiet):stop=max(start+80,limit-140+int(quiet[0])*10)
  midi=tonic+SOLFEGE[degree]
  center=(start+stop)//2;seg=audio[max(0,center*16-2048):center*16+2048].astype(float)
  spectrum=np.abs(np.fft.rfft(seg*np.hanning(len(seg)),n=32768))
  freq=np.fft.rfftfreq(32768,1/16000)
  candidates=np.arange(midi-1.5,midi+1.51,.02)
  salience=[]
  for p in candidates:
   hz=440*2**((p-69)/12)
   salience.append(sum(np.interp(hz*h,freq,spectrum)/h for h in range(1,6)))
  observed=float(candidates[np.argmax(salience)])
  notes.append(dict(index=i+1,start_ms=start,duration_ms=stop-start,midi=midi,degree=degree,
   boundary_tolerance_ms=100,pitch_spectral_deviation_cents=round((observed-midi)*100,1),
   pitch_review='needs_listening' if abs(observed-midi)>.6 else 'spectrum_supports_score_prior',
   split='repeat_section_check' if start>=split else 'development',annotation='score_prior_output_assisted_boundaries_not_human_verified'))
 assert len(notes)==len(degrees)
 p=REF/(key+'_reference.csv')
 with p.open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(notes[0]));w.writeheader();w.writerows(notes)
 recognized=list(csv.DictReader((ROOT/f'build/melody_workbench_20261028/real_audio/{key}/android_notes.csv').open()))
 recognized=[{k:int(v) if k!='confidence' else float(v) for k,v in n.items()} for n in recognized]
 # Pair by temporal overlap, not greedy nearest pitch. One event can match
 # only one expected note: a merged repeated syllable cannot score twice.
 pairs=[];used=set()
 for n in notes:
  options=[]
  for j,a in enumerate(recognized):
   if j in used:continue
   overlap=max(0,min(n['start_ms']+n['duration_ms'],a['start_ms']+a['duration_ms'])-max(n['start_ms'],a['start_ms']))
   if overlap>0:options.append((overlap,-abs(n['start_ms']-a['start_ms']),j))
  if options:
   j=max(options)[2];used.add(j);a=recognized[j]
   pairs.append({**n,'observed_start_ms':a['start_ms'],'observed_duration_ms':a['duration_ms'],'observed_midi':a['midi'],
    'onset_error_ms':a['start_ms']-n['start_ms'],'duration_error_ms':a['duration_ms']-n['duration_ms'],
    'pitch_correct':a['midi']==n['midi']})
  else:pairs.append({**n,'observed_midi':None,'pitch_correct':False})
 metrics={}
 for name in ['development','repeat_section_check']:
  part=[n for n in pairs if n['split']==name];matched=[n for n in part if n['observed_midi'] is not None]
  metrics[name]={'reference_notes':len(part),'matched_notes':len(matched),
    'pitch_correct':sum(n['pitch_correct'] for n in part),
    'pitch_correct_fraction_of_reference':sum(n['pitch_correct'] for n in part)/len(part),
    'onset_mae_ms':float(np.mean([abs(n['onset_error_ms']) for n in matched])),
    'duration_mae_ms':float(np.mean([abs(n['duration_error_ms']) for n in matched])),
    'uncertainty_ms':100,'human_verified_ground_truth':False,'boundary_independent':False}
 (OUT/(key+'_audit.json')).write_text(json.dumps(pairs,ensure_ascii=False,indent=2),encoding='utf8')
 results.append({'name':key,'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
  'reference':str(p),'reference_notes':len(notes),'recognized_notes':len(recognized),'unpaired_recognized_notes':len(recognized)-len(used),
  'metrics':metrics,'limits':'Pitch sequence is score-prior. Boundaries were assisted by previous output and acoustic checks, so onset/duration figures are audit distances, NOT independent timing accuracy. Repeated sections already used in prior development, not held-out. New held-out raw excerpts are separately captured without tuning; no cross-singer accuracy claim.'})
(OUT/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
summary=['# 两份人声的逐音核对','',
 '本表对照谱面主音先验，时间边界为输出与声学辅助候选，尚未经人工逐音听审。以下是可疑分段清单，不宣称真实识谱准确率或独立节奏精度。',
 '', '| 素材 | 参考主音数 | 识别数 | 已配对主音 | 未配对参考音 | 额外分段候选 |', '|---|---:|---:|---:|---:|---:|']
for item in results:
 total=sum(x['matched_notes'] for x in item['metrics'].values())
 summary.append(f"| {'两只老虎' if item['name']=='tigers' else '小星星'} | {item['reference_notes']} | {item['recognized_notes']} | {total} | {item['reference_notes']-total} | {item['unpaired_recognized_notes']} |")
summary+=['','主要可操作位置：','',
 '- 两只老虎：约0.15秒和23.66秒有起音下方短滑音候选，可试听确认后删除多余段，再按需要提前保留音的起点。',
 '- 小星星：约14.36秒、15.50秒附近的同音重复可能被合并，可在长音中间“分开同音”；约17.41秒、21.49秒、35.42秒附近需检查是否多拆，确认后可合并紧邻同音或删除杂音。',
 '- 所有音的候选时间、频谱检查、配对和时长差保留在CSV/JSON；存在不确定性，不根据这些位置在App里硬编码曲谱。',
 '', '额外片段：原录音60–90秒、65–100秒未用于本轮参数修改，已由实际App编译类处理并留有试听及传谱/自主播放仿真。它们来自同一原录音，不代表新歌手泛化。',
 '', '本轮保留通用识别参数，通过可撤销的局部重识别和逐音修正处理模型剩余误分。真实手机收音与最终听感仍需实测。']
(OUT/'识谱核对报告.md').write_text('\n'.join(summary)+'\n',encoding='utf8')
(REF/'README.md').write_text('''# 谱面先验与音频辅助逐音参考

两只老虎64个主音，小星星56个主音。主音来自常规简谱旋律，实际调性通过音频频谱核对；每个音附带声学检查和不确定性。边界锚点为音频辅助候选，标注容差100ms，尚未经人逐音听审，不能称专业人工真值。保留同音重复字，不能将一个长音匹配两次。

前后唱段分成development和repeat_section_check，均是已用过的演示素材。时界候选还参考了旧输出，不能据此声称独立节奏准确率。另从原始音频60–90/65–100秒截取本轮未调参的新片段，保留完整识别试听待听审；仍不是新歌手/新环境泛化。本轮不依据参考修改识谱参数。识谱App不加载这些文件，不按曲名或文件指纹输出固定答案。

report.json报告的是相对这份候选参考的偏差，原始音频和识别试听仍需听感验收。
''',encoding='utf8')
print(json.dumps(results,ensure_ascii=False,indent=2))
