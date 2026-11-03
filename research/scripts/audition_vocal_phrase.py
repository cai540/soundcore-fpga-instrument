"""Offline vocal experiment; separate from the published App recognizer."""
from pathlib import Path
import os,sys,subprocess,json,csv,wave,hashlib,argparse
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--source',default='C:/Users/YOUR_USER/Downloads/audio [vocals] (3).mp3')
parser.add_argument('--start',type=float,default=6.75)
parser.add_argument('--end',type=float,default=34.30)
parser.add_argument('--build-dir',default='build/mono_audition_vocals3_20261028')
parser.add_argument('--output-dir',default='output/vocals3_first_phrase_20261028')
parser.add_argument('--label',default='第一段人声')
parser.add_argument('--vocal-articulation',action='store_true')
args=parser.parse_args()
BUILD=ROOT/args.build_dir;BUILD.mkdir(parents=True,exist_ok=True)
DEST=ROOT/args.output_dir;DEST.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'build/mono_audition_vocals3_20261028/python_deps'))
os.environ['NUMBA_CACHE_DIR']=str(BUILD/'numba_cache')
import librosa

source=Path(args.source)
rate=16000;hop=160;start=args.start;end=args.end
assert end>start>=0
audio=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(source),'-ss',str(start),'-t',str(end-start),
 '-af','pan=mono|c0=0.5*c0+0.5*c1','-ac','1','-ar',str(rate),'-f','f32le','-']),dtype='<f4').copy()
trackfile=BUILD/'pyin_track.npz'
fingerprint=hashlib.sha256(audio.tobytes()).hexdigest()
saved=np.load(trackfile) if trackfile.exists() else None
if saved is not None and 'pcm_sha256' in saved and str(saved['pcm_sha256'])==fingerprint:
 f0=saved['f0'];voiced=saved['voiced'];prob=saved['prob']
else:
 f0,voiced,prob=librosa.pyin(audio,fmin=65.4,fmax=1200,sr=rate,frame_length=1024,hop_length=hop,
  max_transition_rate=20.0,fill_na=np.nan)
 np.savez(trackfile,f0=f0,voiced=voiced,prob=prob,pcm_sha256=fingerprint)
time=np.arange(len(f0))*hop/rate
raw=np.where(np.isfinite(f0),69+12*np.log2(np.maximum(f0,1e-6)/440),np.nan)
rms=librosa.feature.rms(y=audio,frame_length=320,hop_length=hop,center=True)[0][:len(f0)]
floor=max(.0025,float(np.max(rms))*.035)
labels=np.where(voiced & (rms>floor),np.rint(np.nan_to_num(raw,nan=-1)).astype(int),-1)
def runs(a):
 cuts=np.r_[0,np.flatnonzero(a[1:]!=a[:-1])+1,len(a)]
 return [(int(s),int(e),int(a[s])) for s,e in zip(cuts[:-1],cuts[1:])]

# Brief consonants can interrupt periodicity without ending the sung note.
# Fill only bounded same-pitch interruptions, never long rests or full phrases.
for s,e,n in runs(labels):
 if n<0 and e-s<=12 and s>0 and e<len(labels) and labels[s-1]==labels[e] and labels[e]>=0:
  labels[s:e]=labels[e]
# A 70ms median suppresses quantization flutter while keeping short sung notes.
smooth=median_filter(labels,size=7,mode='nearest')
smooth[labels<0]=-1
labels=smooth
for s,e,n in runs(labels):
 if n>=0 and e-s<9:
  left=labels[s-1] if s>0 else -1;right=labels[e] if e<len(labels) else -1
  if left==right and left>=0:labels[s:e]=left
  elif left>=0 and abs(n-left)<=2:labels[s:e]=left
  elif right>=0 and abs(n-right)<=2:labels[s:e]=right
  else:labels[s:e]=-1
notes=[]
for s,e,n in runs(labels):
 if n>=0 and e-s>=9:
  notes.append({'start_ms':round(time[s]*1000),'duration_ms':round(min(e*.01,len(audio)/rate)*1000)-round(time[s]*1000),
    'midi':n,'confidence':float(np.mean(prob[s:e]))})
assert notes
base_note_count=len(notes)
corrections=[]
if args.vocal_articulation:
 # Correct half-semitone quantization flutter only when the continuous F0
 # stays closer to the surrounding stable note than a full semitone.
 original_notes=[n.copy() for n in notes]
 for i,n in enumerate(notes):
  if n['duration_ms']>360:continue
  left=original_notes[i-1] if i>0 else None;right=original_notes[i+1] if i+1<len(notes) else None
  s=n['start_ms']//10;e=(n['start_ms']+n['duration_ms'])//10
  f=raw[s:e];f=f[np.isfinite(f)]
  if not len(f):continue
  pitch=float(np.median(f));replacement=None
  if left and right and left['midi']==right['midi'] and abs(n['midi']-left['midi'])==1 and abs(pitch-left['midi'])<.8:
   replacement=left['midi']
  elif left and n['duration_ms']<=300 and left['duration_ms']>=400 and abs(n['midi']-left['midi'])==1 and \
    n['start_ms']-left['start_ms']-left['duration_ms']<=20 and abs(pitch-left['midi'])<.8:
   replacement=left['midi']
  elif n['duration_ms']<140:
   neighbours=[x for x in (left,right) if x and abs(x['midi']-n['midi'])<=1 and
    (x['duration_ms']>=600 or i==0 and x['duration_ms']>=300)]
   if neighbours:replacement=min(neighbours,key=lambda x:abs(x['midi']-pitch))['midi']
  if replacement is not None and replacement!=n['midi']:
   corrections.append({'time_ms':n['start_ms'],'from':n['midi'],'to':replacement,'reason':'brief_quantization_glide'})
   n['midi']=replacement
 merged=[]
 for n in notes:
  if merged and n['midi']==merged[-1]['midi'] and n['start_ms']-merged[-1]['start_ms']-merged[-1]['duration_ms']<=20:
   merged[-1]['duration_ms']=n['start_ms']+n['duration_ms']-merged[-1]['start_ms']
  else:merged.append(n.copy())
 # A short leading glide may belong to the following first sung note.
 if len(merged)>1 and merged[0]['duration_ms']<140 and merged[0]['midi']==merged[1]['midi'] and \
   merged[1]['start_ms']-merged[0]['start_ms']-merged[0]['duration_ms']<250:
  merged[1]['duration_ms']+=merged[1]['start_ms']-merged[0]['start_ms'];merged[1]['start_ms']=merged[0]['start_ms']
  merged=merged[1:]
 # Repeated syllables of the same pitch need a fresh attack. Require an
 # energy dip with an audible rise on BOTH sides, away from note endpoints.
 energy=median_filter(rms,size=5)
 valleys,_=find_peaks(-np.log(np.maximum(energy,1e-5)),distance=20,prominence=.65)
 notes=[]
 for n in merged:
  s=n['start_ms']//10;e=(n['start_ms']+n['duration_ms'])//10;cuts=[s]
  if e-s>=65:
   for k in valleys:
    if not(s+18<k<e-18) or k-cuts[-1]<18:continue
    low=energy[k]
    if max(energy[max(s,k-12):k])>low*1.75 and max(energy[k+1:min(e,k+13)])>low*1.75:
     cuts.append(int(k))
  cuts.append(e)
  for a,b in zip(cuts[:-1],cuts[1:]):
   notes.append({'start_ms':a*10,'duration_ms':(b-a)*10,'midi':n['midi'],'confidence':float(np.mean(prob[a:b]))})
  if len(cuts)>2:corrections.append({'time_ms':n['start_ms'],'attacks':len(cuts)-1,'reason':'same_pitch_syllable_attacks'})
with (BUILD/'vocal_stable_notes.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=list(notes[0]));writer.writeheader();writer.writerows(notes)
with (BUILD/'pyin_frames.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.writer(f);writer.writerow(['seconds','f0_hz','midi','voiced','probability','rms','stable_midi'])
 writer.writerows(zip(time,f0,raw,voiced,prob,rms,labels))
print(json.dumps({'notes':len(notes),'range':[min(n['midi'] for n in notes),max(n['midi'] for n in notes)],
 'coverage_seconds':sum(n['duration_ms'] for n in notes)/1000,'last_note_seconds':(notes[-1]['start_ms']+notes[-1]['duration_ms'])/1000},indent=2),flush=True)
print('notes:',[(n['start_ms'],n['duration_ms'],n['midi']) for n in notes],flush=True)

# Original-pitch preview: useful for direct comparison with the supplied voice.
# Constant gain and short click-free envelopes do not alter estimated timing.
preview=np.zeros(len(audio),dtype=np.float64)
for n in notes:
 a=round(n['start_ms']*rate/1000);b=min(len(audio),a+round(n['duration_ms']*rate/1000))
 if b<=a:continue
 t=np.arange(b-a)/rate;hz=440*2**((n['midi']-69)/12)
 env=np.minimum(1,np.minimum(t/.012,(b-a-1-np.arange(b-a))/(rate*.018))).clip(0,1)
 preview[a:b]=np.sin(2*np.pi*hz*t)*env*.23
wav=DEST/(args.label+'_稳定识别_原调.wav')
pcm=np.rint(preview*32767).astype('<i2')
with wave.open(str(wav),'wb') as f:f.setparams((1,2,rate,len(pcm),'NONE','not compressed'));f.writeframes(pcm.tobytes())
mp3=wav.with_suffix('.mp3')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-codec:a','libmp3lame','-q:a','2',str(mp3)],check=True)
original=DEST/(args.label+'_原声对照.mp3')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-ss',str(start),'-t',str(end-start),'-vn',
 '-c:a','libmp3lame','-q:a','2',str(original)],check=True)
decoded=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(mp3),'-ac','1','-ar',str(rate),'-f','s16le','-']),dtype='<i2')
assert len(decoded)==len(pcm) and np.abs(decoded.astype(np.int32)).max()<32760
meta={'method':'librosa 0.11 pYIN + bounded same-pitch consonant bridge + short-run stability',
 'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_segment_seconds':[start,end],
 'notes':len(notes),'duration_seconds':len(audio)/rate,'output':str(mp3),'original_clip':str(original),
 'transpose':0,'device_transpose_required':max(0,60-min(n['midi'] for n in notes)),
 'vocal_articulation':args.vocal_articulation,'before_articulation_note_count':base_note_count,'automatic_corrections':corrections,
 'manual_note_changes':False,'uses_song_score_or_hardcoded_melody':False,'implemented_in_published_app':False,
 'physical_recording':False,'reference':'https://librosa.org/doc/0.11.0/generated/librosa.pyin.html'}
(BUILD/'vocal_stable_audition.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
