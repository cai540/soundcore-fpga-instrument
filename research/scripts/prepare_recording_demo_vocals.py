"""Cut the supplied ORIGINAL vocal MP3s into bounded recording-demo inputs."""
from pathlib import Path
import subprocess,json,hashlib,zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/recording_demo_vocals_20261028'
OUT.mkdir(parents=True,exist_ok=True)
items=[
 {'source':Path('C:/Users/YOUR_USER/Downloads/audio [vocals] (3).mp3'),
  'start':6.75,'end':36.75,'filename':'01_人声演示_30秒.mp3',
  'selection':'完整保留已试听的第一段人声，末尾保留约2.7秒原有收尾停顿；没有拼接或变速。'},
 {'source':Path('C:/Users/YOUR_USER/Downloads/audio [vocals] (4).mp3'),
  'start':15.95,'end':51.75,'filename':'02_小星星人声_35.8秒.mp3',
  'selection':'跳过开头广告与演唱前空白；在完整乐句收尾处结束，没有拼接或变速。'},
]
results=[]
for item in items:
 duration=round(item['end']-item['start'],3)
 assert 30<=duration<=40
 path=OUT/item['filename']
 native=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(item['source']),
  '-ss',str(item['start']),'-t',str(duration),'-ac','2','-ar','44100','-f','f32le','-']),dtype='<f4').reshape(-1,2)
 blocks=native[:len(native)//882*882].reshape(-1,882,2)
 block_power=np.mean(blocks.astype(np.float64)**2,axis=(1,2))
 active=block_power>max(.002**2,float(block_power.max())*.08**2)
 active_rms=float(np.sqrt(np.mean(block_power[active])))
 native_peak=float(np.max(np.abs(native)))
 # A single constant gain matches useful recording levels. No limiter,
 # compression, pitch change or time stretching is applied.
 gain=min(.08/active_rms,.85/native_peak)
 # Microfades are inside the existing quiet head/tail, not time stretching.
 filters=(f"atrim=start={item['start']}:end={item['end']},asetpts=PTS-STARTPTS,"
  f'volume={gain:.10f},afade=t=in:st=0:d=0.01,afade=t=out:st={duration-.04:.3f}:d=0.04')
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(item['source']),
  '-map','0:a:0','-vn','-af',filters,'-c:a','libmp3lame','-q:a','2',str(path)],check=True)
 def decode(p,extra=()):
  return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),*extra,
   '-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4')
 output=decode(path)
 reference=decode(item['source'],['-ss',str(item['start']),'-t',str(duration)])
 assert len(output)==len(reference)==round(duration*16000)
 assert np.isfinite(output).all() and np.max(np.abs(output))>.03
 # Re-encoding should retain the supplied voice, not synthesize a melody.
 a=reference[1600:-1600];b=output[1600:-1600]
 corr=float(np.corrcoef(a,b)[0,1]);assert corr>.98,(path,corr)
 channel_pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-']),dtype='<f4')
 channel_peak=float(np.max(np.abs(channel_pcm)));assert channel_peak<.99
 silence=subprocess.run(['ffmpeg','-hide_banner','-i',str(path),'-af','silencedetect=noise=-35dB:d=0.7',
  '-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace')
 assert silence.returncode==0
 (OUT/(path.stem+'_检测.log')).write_text(silence.stderr,encoding='utf-8')
 results.append({'source':str(item['source']),'source_sha256':hashlib.sha256(item['source'].read_bytes()).hexdigest(),
  'source_start_seconds':item['start'],'source_end_seconds':item['end'],'duration_seconds':len(output)/16000,
  'selection':item['selection'],'output':str(path),'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
  'correlation_with_original_clip':corr,'channel_peak':channel_peak,
  'source_active_rms':active_rms,'constant_gain_db':float(20*np.log10(gain)),
  'pitch_shift':0,'speed_ratio':1,'original_voice':True,'synthesized_audio':False})
readme='''这两份是录音演示的原人声素材，保持原始速度与音调，并非电子音识别试听。
仅做剪辑、固定音量调整及安静首尾的极短淡化，不做变速、移调或压缩动态。两份按相近的有效人声音量处理，并预留峰值余量，方便收音。

01_人声演示_30秒.mp3：原文件 audio [vocals] (3).mp3 的6.75–36.75秒，完整保留第一段人声及约2.7秒原有收尾停顿。
02_小星星人声_35.8秒.mp3：原文件 audio [vocals] (4).mp3 的15.95–51.75秒，已跳过广告和开唱前的长空白，在乐句结尾截断。

两份均小于现有App的40秒上限。可以在另一台设备播放，供手机麦克风录音，也可作为文件导入的素材。
手机对着外放收音会受距离、回声和播放音量影响，需要在演示使用的设备与环境上提前验证。

此前听感较好的版本是电脑端改进识别实验。当前已发布App尚未接入该改进算法，不能把这些素材或电脑端试听当作手机端已验收的证据。
'''
(OUT/'素材说明.txt').write_text(readme,encoding='utf-8-sig')
(OUT/'剪辑与校验记录.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT/'两份录音演示人声素材.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for item in items:z.write(OUT/item['filename'],item['filename'])
 z.write(OUT/'素材说明.txt','素材说明.txt')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for item in results:
  name=Path(item['output']).name
  assert hashlib.sha256(z.read(name)).hexdigest()==item['output_sha256']
print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)
