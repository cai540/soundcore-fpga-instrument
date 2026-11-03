"""Offline arrangement-distance metrics and source-clock A/B listening artifacts."""
from pathlib import Path
import json,csv,subprocess,wave
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/vocal_phrase_20261029'
OUT=ROOT/'output/vocal_phrase_20261029';OUT.mkdir(exist_ok=True)
results=json.loads((B/'audio_results.json').read_text(encoding='utf8'))
titles={'zuguo':'我和我的祖国','chilege':'敕勒歌','qiansixi':'牵丝戏','lantingxu':'兰亭序',
 'tigers':'两只老虎','twinkle':'小星星','tigers_holdout':'两只老虎_保留片段','twinkle_holdout':'小星星_保留片段'}

def readnotes(path):
 return [{'start':int(n['start_ms']),'end':int(n['start_ms'])+int(n['duration_ms']),'midi':int(n['midi'])}
  for n in csv.DictReader(path.open(encoding='utf8'))]
def labels(notes,n):
 a=np.full(n,-1)
 for note in notes:a[max(0,note['start']//10):min(n,(note['end']+9)//10)]=note['midi']
 return a
def refs(name):
 table=ROOT/f'songs/product_song_review/{"wodezuguo" if name=="zuguo" else name}.csv'
 return [{'start':round(float(n['source_start_s'])*1000),'end':round(float(n['source_end_s'])*1000),
  'midi':int(n['source_midi'])} for n in csv.DictReader(table.open(encoding='utf8')) if n['midi']!='rest']
def waveform(notes,length):
 out=np.zeros(length,dtype='<i2');phase=0.
 for n in notes:
  start=max(0,n['start']*16);count=min(length-start,(n['end']-n['start'])*16)
  if count<=0:continue
  t=np.arange(count);env=np.minimum(1,np.minimum(t/(16000*.012),(count-1-t)/(16000*.018))).clip(0)
  omega=2*np.pi*440*2**((n['midi']-69)/12)/16000
  out[start:start+count]=(np.sin(phase+omega*t)*env*7500).astype('<i2');phase=(phase+omega*count)%(2*np.pi)
 return out
def mp3(data,path):
 # Feed raw PCM to ffmpeg; no duplicate large WAV files in the deliverable.
 subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar','16000','-ac',str(1 if data.ndim==1 else 2),
  '-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(path)],input=data.astype('<i2').tobytes(),check=True)
def metrics(old,new,reference,offset,length):
 ref=[{**n,'start':n['start']-offset,'end':n['end']-offset} for n in reference]
 expected=labels(ref,length//10);mask=np.zeros(len(expected),bool)
 for n in ref:
  # Conservative interior excludes 150ms at each editorial reference boundary.
  a=max(0,(n['start']+150)//10);b=min(len(mask),(n['end']-150)//10)
  if b>a:mask[a:b]=True
 out={}
 for key,notes in [('old',old),('new',new)]:
  pred=labels(notes,len(expected));valid=mask&(expected>=0)
  short=sum(n['end']-n['start']<200 for n in notes)
  out[key]={'notes':len(notes),'sub200ms_notes':short,'reference_interior_frames':int(valid.sum()),
   'same_pitch_frames':int(((pred==expected)&valid).sum()),'covered_frames':int(((pred>=0)&valid).sum()),
   'pitch_agreement':float(np.mean(pred[valid]==expected[valid])) if valid.any() else None,
   'voiced_coverage':float(np.mean(pred[valid]>=0)) if valid.any() else None}
 return out

summary=[]
for item in results:
 if item['status']!='ok':continue
 old=Path(item['old']);new=Path(item['new']);name=item['name'];window=item['window']
 oldpath=old/('android_notes.csv' if window=='nursery' else 'notes.csv')
 a=readnotes(oldpath);b=readnotes(new/'notes.csv');length=item['source_ms']*16
 m={'name':name,'window':window,'old_notes':len(a),'new_notes':len(b)}
 if name in ['zuguo','chilege']:
  offset=round((47.09 if name=='zuguo' else 30.97)*1000) if window=='first40' else int(window[-2:])*40000
  m['reference_distance']=metrics(a,b,refs(name),offset,item['source_ms'])
 if window in ['first40','nursery'] or window in ['chunk_02','chunk_03'] and name in ['zuguo','chilege']:
  d=OUT/titles[name];d.mkdir(exist_ok=True)
  suffix='40秒' if window=='first40' else '复核80至120秒' if window=='chunk_02' else '复核120至160秒' if window=='chunk_03' else '演示片段'
  oldpcm=np.fromfile(old/'original_pitch.s16',dtype='<i2') if (old/'original_pitch.s16').exists() else waveform(a,length)
  pcm=np.fromfile(new/'original_pitch.s16',dtype='<i2');assert len(pcm)==len(oldpcm)==length
  voice=np.fromfile(new/'analysis.f32',dtype='<f4');assert len(voice)==length
  mp3(pcm,d/f'{titles[name]}_新版主音_{suffix}.mp3')
  mp3(np.column_stack([oldpcm,pcm]),d/f'{titles[name]}_旧版左_新版右_{suffix}.mp3')
  mp3(np.column_stack([(voice.clip(-1,1)*28000).astype('<i2'),pcm]),d/f'{titles[name]}_人声左_新版右_{suffix}.mp3')
  (d/f'{titles[name]}_新版_{suffix}.csv').write_bytes((new/'notes.csv').read_bytes())
  if (new/'app_adapted.mid').exists():(d/f'{titles[name]}_设备适配_{suffix}.mid').write_bytes((new/'app_adapted.mid').read_bytes())
  if name in ['zuguo','chilege']:
   reference=[{**n,'start':max(0,n['start']-offset),'end':min(length//16,n['end']-offset)}
    for n in refs(name) if n['end']>offset and n['start']<offset+length//16]
   mp3(waveform(reference,length),d/f'{titles[name]}_旧精修参考_原时间轴_{suffix}.mp3')
 summary.append(m)
for name in ['zuguo','chilege']:
 d=OUT/titles[name];rows=[x for x in results if x['name']==name and x['window'].startswith('chunk_')]
 length=max(int(x['window'][-2:])*40000*16+len(np.fromfile(Path(x['new'])/'original_pitch.s16',dtype='<i2'))
  for x in rows if x['status']=='ok')
 full=np.zeros(length,dtype='<i2')
 for x in rows:
  if x['status']!='ok':continue
  a=np.fromfile(Path(x['new'])/'original_pitch.s16',dtype='<i2');s=int(x['window'][-2:])*40000*16
  full[s:s+len(a)]=a
 mp3(full,d/f'{titles[name]}_全文件分段复算_新版.mp3')
 # Full-window boundary continuity is not a single continuous full-song run.
(B/'comparison_metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'对照统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
for x in summary:
 if 'reference_distance' in x and x['window'] in ['first40','chunk_03']:print(x,flush=True)
print('A/B previews preserve identical source clocks; old curated models are offline references only.')
