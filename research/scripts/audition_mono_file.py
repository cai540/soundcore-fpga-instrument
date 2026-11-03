"""Use the actual compiled Android recognizer to audition a supplied 40-second clip."""
from pathlib import Path
import subprocess,json,os,hashlib,wave,argparse,shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--source',default='C:/Users/YOUR_USER/xwechat_files/wxid_nc4c6jcrry7e22_2653/msg/file/2026-10/生日快乐歌（纯音乐）-曾经的回忆.mp3')
parser.add_argument('--start',type=float,default=0)
parser.add_argument('--end',type=float,default=40)
parser.add_argument('--build-dir',default='build/mono_audition_birthday_20261028')
parser.add_argument('--output-dir',default='output/birthday_mono_audition_20261028')
parser.add_argument('--label',default='生日快乐歌_40秒')
args=parser.parse_args()
OUT=ROOT/args.build_dir;OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path(args.source)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,sample_rate,channels','-of','json',str(SOURCE)]))
stream=next(s for s in probe['streams'] if s['codec_type']=='audio')
rate=int(stream['sample_rate']);channels=int(stream['channels'])
assert channels in (1,2)
end=min(args.end,float(probe['format']['duration']))
duration=end-args.start;assert 0.25<=duration<=40 and args.start>=0
cmd=['ffmpeg','-v','error','-y','-i',str(SOURCE),'-ss',str(args.start),'-t',str(duration),'-vn']
if channels==2:cmd+=['-af','pan=mono|c0=0.5*c0+0.5*c1']
cmd+=['-ac','1','-f','f32le',str(OUT/'input.f32')]
subprocess.run(cmd,check=True)
jdk=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin')
classes=ROOT/'app/android/app/build/tmp/kotlin-classes/debug'
stdlib=next(Path('C:/Users/YOUR_USER/.gradle/caches/modules-2/files-2.1/org.jetbrains.kotlin/kotlin-stdlib/2.2.21').rglob('*.jar'))
cp=os.pathsep.join(map(str,[classes,stdlib,OUT]))
helper=ROOT/'build/mono_audition_birthday_20261028/RecognizeAudio.java'
if helper.parent!=OUT:shutil.copy2(helper,OUT/helper.name)
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-cp',cp,str(OUT/'RecognizeAudio.java')],check=True)
run=subprocess.run([str(jdk/'java.exe'),'-cp',cp,'RecognizeAudio',str(OUT),str(rate)],capture_output=True,text=True)
(OUT/'recognition.log').write_text(run.stdout+run.stderr,encoding='utf-8')
print(run.stdout+run.stderr,flush=True)
assert run.returncode==0
info=json.loads((OUT/'recognition.json').read_text())
audio=np.fromfile(OUT/'recognized.s16',dtype='<i2')
# Keep the selected source timeline, including any missed notes/rests.
preview=np.zeros(round(duration*16000),dtype='<i2');offset=info['first_ms']*16
preview[offset:min(len(preview),offset+len(audio))]=audio[:max(0,min(len(audio),len(preview)-offset))]
DEST=ROOT/args.output_dir;DEST.mkdir(parents=True,exist_ok=True)
wav=DEST/(args.label+'_识别试听.wav')
with wave.open(str(wav),'wb') as w:
 w.setparams((1,2,16000,len(preview),'NONE','not compressed'));w.writeframes(preview.tobytes())
mp3=wav.with_suffix('.mp3')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-codec:a','libmp3lame','-q:a','2',str(mp3)],check=True)
original=DEST/(args.label+'_原声对照.mp3')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(SOURCE),'-ss',str(args.start),'-t',str(duration),'-vn','-c:a','libmp3lame','-q:a','2',str(original)],check=True)
decoded=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(mp3),'-f','s16le','-ac','1','-ar','16000','-']),dtype='<i2')
assert len(decoded)==len(preview) and np.max(np.abs(decoded.astype(np.int32)))<32760
metrics={**info,'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'source_segment_seconds':[args.start,end],'decoder':'ffmpeg stereo channel average; App resampler and recognizer unchanged',
 'recognizer_class_sha256':hashlib.sha256((classes/'cn/soundcore/instrument/MelodyRecognition.class').read_bytes()).hexdigest(),
 'manual_note_changes':False,'reference_timbre':'App sine preview; not physical FPGA recording',
 'output':str(mp3),'original_clip':str(original),'decoded_duration_seconds':len(decoded)/16000,'peak':int(np.max(np.abs(decoded.astype(np.int32))))}
(OUT/'audition.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(metrics,ensure_ascii=False,indent=2),flush=True)
