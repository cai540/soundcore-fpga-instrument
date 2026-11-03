"""Offline labelled diagnosis only. No labels are consumed by the App."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_refine_20261029'
OLD=ROOT/'build/vocal_syllable_20261029/audio'
cases=[('zuguo','first40','首句相邻半音',1.45,2.28,[70,69]),
 ('zuguo','first40','滑入低音',15.70,16.25,None),
 ('zuguo','first40','我',11.30,11.75,[74]),
 ('zuguo','first40','每',27.21,27.93,[76]),
 ('zuguo','first40','路前滑入',36.53,37.52,[64]),
 ('zuguo','first40','路尾滑',36.73,37.52,[64]),
 ('chilege','first40','羊',4.85,5.45,[57]),
 ('chilege','first40','亮',19.15,19.83,[69]),
 ('chilege','first40','杆',27.91,29.33,[59]),
 ('chilege','chunk_02','盏',1.68,3.30,[59]),
 ('chilege','chunk_02','下',16.36,19.05,[69]),
 ('chilege','chunk_02','茫',30.24,31.68,[74,66]),
 ('chilege','chunk_03','川',32.14,35.16,[71]),
 ('chilege','chunk_04','草',14.74,16.50,[59]),
 ('chilege','chunk_04','见',16.62,17.88,[64])]
def inside(path,start,end):
 out=[]
 for x in csv.DictReader(path.open(encoding='utf8')):
  s=int(x['start_ms'])/1000;e=s+int(x['duration_ms'])/1000
  if min(e,end)-max(s,start)>=.08:
   out.append({'start':s,'end':e,'midi':int(x['midi'])})
 return out
report=[]
for name,window,word,start,end,ref in cases:
 offset=47.09 if name=='zuguo' and window=='first40' else 30.97 if window=='first40' else int(window[-2:])*40
 a=inside(OLD/name/window/'notes.csv',start,end);b=inside(B/'audio'/name/window/'notes.csv',start,end)
 report.append({'name':name,'window':window,'word':word,'relative_seconds':[start,end],
  'source_seconds':[round(start+offset,2),round(end+offset,2)],'reference_pitch':ref,'old':a,'new':b})
(B/'position_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# 0.5与0.6的具体位置对照','',
 '时间为原始人声文件的时间。首40秒试听对应祖国47.09–87.09秒、敕勒30.97–70.97秒。旧精修词界可能偏移，表内差异是诊断线索，不能全部视为声学真值错误。','',
 '|曲目/位置|原声时间/s|旧0.5音高事件|新0.6音高事件|精修参考|','|---|---|---|---|---|']
for x in report:
 title='我和我的祖国' if x['name']=='zuguo' else '敕勒歌'
 text=lambda a:' → '.join(str(n['midi']) for n in a) or '无'
 lines.append(f"|{title}·{x['word']}|{x['source_seconds'][0]:.2f}–{x['source_seconds'][1]:.2f}|{text(x['old'])}|{text(x['new'])}|{x['reference_pitch']}|")
lines+=['','音符编号为MIDI音高；同一个编号连续出现代表再次起音。真实同音重复仍需保留，不能只按编号相同全部合并。',
 '“草”等词界可能跨真实换音。PCM谱支持与精修不完全相同时，保留不确定性，不强制改成谱面某一音。']
(B/'position_comparison.md').write_text('\n'.join(lines),encoding='utf8');print('\n'.join(lines))
