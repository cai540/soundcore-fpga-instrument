from pathlib import Path
import os,subprocess,json,wave,sys,argparse,xml.etree.ElementTree as ET
import numpy as np
from simulation_sources import iverilog_sources
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
parser=argparse.ArgumentParser();parser.add_argument('--analyze-only',action='store_true');parser.add_argument('--out',default='build/acceptance_20261102');parser.add_argument('--source-build');parser.add_argument('--compact',action='store_true');args=parser.parse_args();B=R/args.out;B.mkdir(parents=True,exist_ok=True)
if not args.analyze_only:
 sources=list((R/'rtl').glob('*.v'));options=[]
 if args.source_build:
  build=R/args.source_build;sources=[Path(x.get('path'))for x in ET.parse(build/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')if x.get('type')=='file.verilog' and Path(x.get('path')).name not in ['pressure_i2s_panel_oled_ble_experiment_top.v','soundcore_melody_top.v','audio_pll_12m288.v']];options=['-I',str(build)]
 binary=B/'tb_tools_voices_i2s.vvp';bench=B/'tb_tools_voices_i2s.v'
 text=(R/'tb/tb_tools_voices_i2s.v').read_text().replace('build/acceptance_20261102/voices32_i2s.txt',(B/'voices32_i2s.txt').as_posix())
 if args.compact:
  for a,b in [('30384','15636'),('28384','14336'),('20384','10240'),('4000','2048')]:text=text.replace(a,b)
 bench.write_text(text)
 sources=iverilog_sources(sources,B/'simulation_sources',R)
 r=subprocess.run([str(BIN/'iverilog.exe'),'-g2012',*options,'-s','tb_tools_voices_i2s','-o',str(binary),str(bench),*map(str,sources)],cwd=R,capture_output=True,text=True)
 assert r.returncode==0,(r.returncode,r.stderr)
 r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=900)
 (B/'tb_tools_voices_i2s.log').write_text(r.stdout+r.stderr);print(r.stdout,flush=True);assert r.returncode==0 and 'PASS'in r.stdout
x=np.loadtxt(B/'voices32_i2s.txt');assert len(x)==(8192 if args.compact else 16384)
fft=np.abs(np.fft.rfft(x*np.hanning(len(x))));hz=np.fft.rfftfreq(len(x),1/48000)
checks=[];t=np.arange(len(x))/48000
freqs=440*2**((np.arange(60,92)-69)/12)
matrix=np.column_stack([fn(2*np.pi*f*t)for f in freqs for fn in(np.sin,np.cos)]+[np.ones(len(x))])
coeff=np.linalg.lstsq(matrix,x,rcond=None)[0];amplitudes=np.hypot(coeff[:-1:2],coeff[1:-1:2])
residual_rms=float(np.sqrt(np.mean((x-matrix@coeff)**2)));signal_rms=float(np.sqrt(np.mean(x*x)))
assert residual_rms/signal_rms<.02,(residual_rms,signal_rms)
for midi in range(60,92):
 target=440*2**((midi-69)/12);indices=np.flatnonzero(abs(hz-target)<5)
 idx=indices[np.argmax(fft[indices])];amplitude=float(amplitudes[midi-60])
 checks.append(dict(midi=midi,target_hz=target,fft_peak_hz=float(hz[idx]),joint_sinusoidal_fit_amplitude=amplitude))
 assert abs(hz[idx]-target)<4 and amplitude>100,checks[-1]
with wave.open(str(B/'32声部_I2S仿真试听.wav'),'wb')as f:f.setparams((1,2,48000,0,'NONE','not compressed'));f.writeframes(x.astype('<i2').tobytes())
(B/'voices32_results.json').write_text(json.dumps(dict(source='decoded actual RTL I2S, not hardware',voices=32,sample_rate=48000,throughput=1536000,notes=checks,peak=int(max(abs(x))),joint_fit_residual_rms=residual_rms,signal_rms=signal_rms,residual_ratio=residual_rms/signal_rms,max_frame_cycles=225),indent=2))
print('PASS:32 distinct I2S FFT fundamentals independently checked')
