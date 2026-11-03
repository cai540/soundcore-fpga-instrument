"""Offline analysis of EXPORTED LAB CSV data. Never fabricates board measurements.
Column indexes are zero-based; timestamps are seconds after --time-scale.
"""
from pathlib import Path
import argparse,json,wave
import numpy as np

def load(args):
 x=np.genfromtxt(args.csv,delimiter=',',skip_header=args.skip_rows)
 if x.ndim!=2:raise ValueError('CSV must contain time and channel columns')
 x=x[np.isfinite(x[:,args.time])];t=x[:,args.time]*args.time_scale
 if len(t)<100 or np.any(np.diff(t)<=0):raise ValueError('Need monotonically increasing timestamps and >=100 samples')
 return x,t

def pcm_from_i2s(t,bclk,lrclk,data,threshold=1.65):
 edges=np.flatnonzero((bclk[1:]>=threshold)&(bclk[:-1]<threshold))+1
 times=[];words=[];prior=None;bit=99;word=0
 for idx in edges:
  ws=int(lrclk[idx]>=threshold)
  if ws!=prior:
   bit=0 if prior is not None else 99;word=0;prior=ws
  elif ws==0 and bit<16:
   word=(word<<1)|int(data[idx]>=threshold);bit+=1
   if bit==16:times.append(t[idx]);words.append(word-65536 if word&32768 else word)
 return np.array(times),np.array(words,dtype=np.int16)

def latency(t,pressure,at,audio,input_step,output_step):
 baseline=float(np.median(pressure[:max(10,len(pressure)//10)]))
 before=np.flatnonzero(pressure>=baseline+input_step)
 after=np.flatnonzero(np.abs(audio.astype(float))>=output_step)
 if len(before)==0 or len(after)==0:raise ValueError('No threshold crossing. Check columns, thresholds and trigger capture.')
 start=float(t[before[0]]);end=float(at[after[0]])
 return dict(input_baseline_v=baseline,input_excursion_threshold_v=input_step,output_absolute_threshold=output_step,
             input_time_s=start,output_time_s=end,latency_ms=(end-start)*1000,
             pretrigger_audio_invalid=end<start,below_5ms=0<end-start<.005)

def spectrum(pcm,rate):
 y=pcm.astype(float);y-=np.mean(y);n=len(y)
 if n<256:raise ValueError('Need at least256 decoded audio samples')
 magnitude=np.abs(np.fft.rfft(y*np.hanning(n)));freq=np.fft.rfftfreq(n,1/rate)
 maxima=np.flatnonzero((magnitude[1:-1]>magnitude[:-2])&(magnitude[1:-1]>=magnitude[2:]))+1
 candidates=maxima[(freq[maxima]>50)&(freq[maxima]<min(6000,rate/2))]
 chosen=candidates[np.argsort(magnitude[candidates])[-40:]][::-1]
 return [dict(hz=float(freq[k]),relative_db=float(20*np.log10(max(magnitude[k],1e-9)/max(magnitude.max(),1))))for k in chosen]

def verify_voices(pcm,rate,count):
 """Spectral presence of the default diagnostic notes, not proof of independence."""
 if len(pcm)/rate<.30:raise ValueError('Voice verification needs >=0.30 seconds of steady-state decoded PCM')
 y=pcm.astype(float);y-=np.mean(y);n=len(y)
 magnitude=np.abs(np.fft.rfft(y*np.hanning(n)));freq=np.fft.rfftfreq(n,1/rate)
 reference=max(float(magnitude.max()),1e-9);rows=[]
 for midi in range(60,60+count):
  target=440*2**((midi-69)/12);tolerance=max(1.5*rate/n,target*.006)
  candidates=np.flatnonzero((np.abs(freq-target)<=tolerance)&(np.arange(len(freq))>0)&(np.arange(len(freq))<len(freq)-1))
  k=int(candidates[np.argmax(magnitude[candidates])])
  db=float(20*np.log10(max(float(magnitude[k]),1e-9)/reference))
  peak=bool(magnitude[k]>magnitude[k-1] and magnitude[k]>=magnitude[k+1])
  rows.append(dict(midi=midi,target_hz=target,peak_hz=float(freq[k]),error_hz=float(freq[k]-target),
                   relative_db=db,tolerance_hz=tolerance,present=peak and db>=-30))
 return dict(expected=count,found=sum(x['present']for x in rows),passed=all(x['present']for x in rows),
             criterion='local FFT peak within declared resolution tolerance and >=-30dB relative to strongest peak',
             independent_gate_and_pitch_not_tested=True,notes=rows)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['i2s','speaker']);p.add_argument('csv',type=Path)
 p.add_argument('--out',type=Path,default=Path('lab_result'));p.add_argument('--skip-rows',type=int,default=1)
 p.add_argument('--time',type=int,default=0);p.add_argument('--time-scale',type=float,default=1)
 p.add_argument('--pressure',type=int,default=1);p.add_argument('--bclk',type=int,default=2);p.add_argument('--lrclk',type=int,default=3);p.add_argument('--din',type=int,default=4)
 p.add_argument('--positive',type=int,default=2);p.add_argument('--negative',type=int,default=3)
 p.add_argument('--logic-threshold',type=float,default=1.65);p.add_argument('--input-step',type=float,default=.05)
 p.add_argument('--output-step',type=float);p.add_argument('--cutoff',type=float,default=8000)
 p.add_argument('--spectrum-only',action='store_true',help='Decode steady-state I2S without a sensor-trigger test')
 p.add_argument('--voices',type=int,choices=(4,8,16,32),help='Check default diagnostic C4-upward fundamentals; capture >=0.30s steady state')
 a=p.parse_args()
 if a.input_step<=0 or (a.output_step is not None and a.output_step<=0):raise ValueError('Thresholds must be positive and declared before measurement')
 x,t=load(a);a.out.mkdir(parents=True,exist_ok=True)
 result=dict(source=str(a.csv.resolve()),source_kind='physical CSV supplied by operator',mode=a.mode)
 if a.mode=='i2s':
  at,pcm=pcm_from_i2s(t,x[:,a.bclk],x[:,a.lrclk],x[:,a.din],a.logic_threshold)
  if len(at)<256:raise ValueError('Too few I2S words. Need standard Philips I2S,16 data bits,32-bit slots; check thresholds/sample rate.')
  rate=int(round(1/np.median(np.diff(at))));jitter=float(np.max(abs(np.diff(at)*rate-1)))
  if rate<8000 or rate>96000 or jitter>.05:raise ValueError(f'Decoded sample timing invalid: rate={rate}, relative jitter={jitter}. Check sampling rate or skipped CSV rows.')
  result.update(sample_rate_hz=rate,words=len(pcm),sample_timing_relative_jitter=jitter,peaks=spectrum(pcm,rate))
  if a.voices:result['diagnostic_spectral_presence']=verify_voices(pcm,rate,a.voices)
  if not a.spectrum_only:result.update(latency(t,x[:,a.pressure],at,pcm,a.input_step,a.output_step or 64))
  with wave.open(str(a.out/'decoded_i2s.wav'),'wb')as f:f.setparams((1,2,rate,0,'NONE','NONE'));f.writeframes(pcm.astype('<i2').tobytes())
 else:
  rate=1/np.median(np.diff(t));cut=a.cutoff
  if rate<2e6 or cut<=0 or cut>=rate/2:raise ValueError('Capture Class-D output at >=2MSa/s; cutoff must be below Nyquist')
  h=np.sinc(2*cut/rate*(np.arange(511)-255))*np.hamming(511);h/=h.sum()
  raw=x[:,a.positive]-x[:,a.negative];raw-=np.median(raw[:max(10,len(raw)//10)])
  filtered=np.convolve(raw,h,mode='full')[:len(raw)]
  result.update(latency(t,x[:,a.pressure],t,filtered,a.input_step,a.output_step or .02))
  result.update(filter='causal511-tap Hamming FIR',filter_cutoff_hz=cut,filter_group_delay_ms=255/rate*1000,delay_subtracted=False)
  np.savetxt(a.out/'filtered_speaker.csv',np.column_stack([t,filtered]),delimiter=',',header='time_s,differential_audio_v',comments='')
 (a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
 if result.get('pretrigger_audio_invalid'):raise SystemExit('Audio already present before input threshold: this capture is not a valid latency test.')
 if result.get('diagnostic_spectral_presence',{}).get('passed')is False:raise SystemExit('Some diagnostic fundamentals are missing: keep this capture and investigate. No acceptance pass was issued.')

if __name__=='__main__':main()
