"""Add uniformly fixed 40–80s listening excerpts from this run's new outputs.
No recognition rerun, correction or historical score is involved.
"""
from pathlib import Path
import json,hashlib,subprocess,wave,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/generic_four_vocals_20261028';OUT=ROOT/'output/generic_four_vocals_20261028'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((OUT/'SHA256.json').read_text(encoding='utf8'))
for name,h in old.items():assert sha(OUT/name)==h,'Existing experiment output changed: '+name
record=json.loads((B/'release.json').read_text(encoding='utf8'))
def mp3(pcm,path):
 wpath=path.with_suffix('.wav')
 with wave.open(str(wpath),'wb') as w:
  w.setnchannels(1 if pcm.ndim==1 else pcm.shape[1]);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm.astype('<i2').tobytes())
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(wpath),'-c:a','libmp3lame','-q:a','2',str(path)],check=True)
for s in record['sources']:
 d=B/s['name']/'chunk_01';out=OUT/s['title'];meta=json.loads((d/'result.json').read_text(encoding='utf8'))
 voice=np.fromfile(d/'analysis.f32',dtype='<f4');melody=np.fromfile(d/'original_pitch.s16',dtype='<i2')
 assert len(voice)==len(melody)==640000
 mp3(melody,out/(s['title']+'_固定40至80秒_原调.mp3'))
 mp3(np.column_stack([(voice.clip(-1,1)*28000).astype('<i2'),melody]),out/(s['title']+'_固定40至80秒_原声左算法右.mp3'))
 s['fixed40_80']={**meta,'source_start_seconds':40,'source_end_seconds':80,'copied_from_this_run_window':1,'correction_applied':False}
record['listening_selection_note']='Energy-only first selection is not verified vocal activity detection. All four additionally include the same fixed source interval 40–80s.'
(B/'release.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'复算记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'evidence/release.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
readme=OUT/'先读我.md'
readme.write_text(readme.read_text(encoding='utf8')+'''
## 额外核对

四首都额外提供了原文件固定40–80秒的原调及左右声道对照，取自本次已经重新计算的第2个窗口，不调用历史建模结果。

能量选段只代表有明显声音，不保证是独唱。《兰亭序》的自动首段从0.49秒开始，可能包含残留前奏；建议同时听固定40–80秒版本。两份结果都保留，未为了好听删除疑似杂音。

完整文件分段中，《我和我的祖国》200秒之后的末段没有找到稳定旋律，保留为空白并保留失败日志；《牵丝戏》有2个窗口的识别音域超过设备35音跨度，原调诊断试听照常保留，但没有伪造可上传版本。是否为误识音、和声或源录音问题，需要听审，不能仅凭这些统计断言。
''',encoding='utf8')
for p in [ROOT/'scripts/finish_four_vocals.py']:(OUT/'evidence'/p.name).write_bytes(p.read_bytes())
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'四首人声_通用算法复算试听.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h,name
print('Verified',len(files),'files;',len(record['sources']),'sources; no corrections; no programming')
