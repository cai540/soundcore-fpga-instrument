"""Inspect an operator-exported steady-state PCM WAV/CSV, never synthesize test evidence.
Raw high-rate I2S may be decoded/exported by the instrument first to avoid multi-GB CSVs.
"""
from pathlib import Path
import argparse,hashlib,json,wave
import numpy as np
from lab_audio_inspect import verify_voices,spectrum

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('file',type=Path)
 p.add_argument('--voices',type=int,choices=(4,8,16,32),required=True)
 p.add_argument('--measured-rate',type=float,required=True,help='LRCLK measured with the laboratory instrument, in Hz')
 p.add_argument('--out',type=Path,required=True);p.add_argument('--column',type=int,default=1)
 p.add_argument('--skip-rows',type=int,default=1);p.add_argument('--skip-seconds',type=float,default=0)
 p.add_argument('--provenance',choices=('laboratory','rtl-simulation','synthetic-selftest'),default='laboratory')
 a=p.parse_args();assert 8000<a.measured_rate<96001
 header_rate=None
 if a.file.suffix.lower()=='.wav':
  with wave.open(str(a.file),'rb')as f:
   if f.getsampwidth()!=2 or f.getcomptype()!='NONE':raise ValueError('Export uncompressed signed16-bit PCM WAV')
   header_rate=f.getframerate();data=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,f.getnchannels())[:,0]
 else:
  x=np.genfromtxt(a.file,delimiter=',',skip_header=a.skip_rows)
  if x.ndim!=2 or a.column>=x.shape[1]:raise ValueError('Need a valid PCM column; do not supply raw I2S bits here')
  data=x[:,a.column]
 if not np.all(np.isfinite(data)) or np.max(np.abs(data))==0:raise ValueError('Invalid/empty PCM')
 if header_rate and abs(header_rate-a.measured_rate)/header_rate>.01:raise ValueError('WAV header and measured LRCLK differ by >1%; check export')
 data=data[round(a.skip_seconds*a.measured_rate):]
 check=verify_voices(data,a.measured_rate,a.voices)
 result=dict(source=str(a.file.resolve()),source_sha256=hashlib.sha256(a.file.read_bytes()).hexdigest(),
   provenance=a.provenance,physical_measurement_claimed=a.provenance=='laboratory',
   lrclk_hz_entered_by_operator=a.measured_rate,wav_header_rate=header_rate,samples=len(data),
   duration_s=len(data)/a.measured_rate,resolution_hz=a.measured_rate/len(data),
   diagnostic_spectral_presence=check,throughput_if_independence_and_audibility_verified=a.voices*a.measured_rate,
   core_scoring_complete=False,remaining=['physical audibility','independent gate/retune demonstration','RTL hardware-chain inspection'])
 a.out.mkdir(parents=True,exist_ok=True)
 (a.out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 np.savetxt(a.out/'expected_peaks.csv',np.array([[r['midi'],r['target_hz'],r['peak_hz'],r['relative_db'],int(r['present'])]for r in check['notes']]),delimiter=',',header='midi,target_hz,peak_hz,relative_db,present',comments='')
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 n=len(data);mag=np.abs(np.fft.rfft((data-data.mean())*np.hanning(n)));hz=np.fft.rfftfreq(n,1/a.measured_rate)
 db=20*np.log10(np.maximum(mag,1e-12)/mag.max());fig,ax=plt.subplots(figsize=(13,4.5))
 ax.plot(hz,db,color='#087e8b',lw=.8)
 for row in check['notes']:
  ax.axvline(row['target_hz'],color='green' if row['present']else 'red',alpha=.3,lw=.8)
 ax.set(xlim=(230,1650),ylim=(-70,3),xlabel='Frequency / Hz',ylabel='Relative magnitude / dB',title=f'{a.provenance}: {check["found"]}/{a.voices} expected peaks; Fs={a.measured_rate:g}Hz')
 ax.grid(alpha=.2);fig.tight_layout();fig.savefig(a.out/'spectrum.png',dpi=170);plt.close(fig)
 print(json.dumps({k:v for k,v in result.items()if k!='diagnostic_spectral_presence'},ensure_ascii=False,indent=2))
 if not check['passed']:raise SystemExit('Missing peaks: retain the original capture and investigate; no acceptance pass')
if __name__=='__main__':main()
