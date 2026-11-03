from pathlib import Path
import argparse,json,subprocess,wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'build/handpan_trial_20261102/tests';O.mkdir(parents=True,exist_ok=True)
B=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
p=argparse.ArgumentParser();p.add_argument('--render',action='store_true');a=p.parse_args()
binary=O/('handpan_render.vvp'if a.render else'handpan_unit.vvp')
run=subprocess.run([str(B/'iverilog.exe'),'-g2012','-s','tb_handpan_modal32','-o',str(binary),str(R/'tb/tb_handpan_modal32.v'),str(R/'rtl/handpan_modal32.v'),str(R/'rtl/note_step_table72.v')],cwd=R,capture_output=True,text=True)
assert run.returncode==0,run.stderr
if not a.render:
 run=subprocess.run([str(B/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=180)
 (O/'modal.log').write_text(run.stdout+run.stderr,encoding='utf8');print(run.stdout,flush=True)
 assert run.returncode==0 and 'PASS:' in run.stdout
else:
 rows=[]
 def render(style):
  pcm=O/f'style{style}.txt'
  with (O/f'render{style}.log').open('w',encoding='utf8')as log:
   result=subprocess.run([str(B/'vvp.exe'),str(binary),'+render=1',f'+style={style}',f'+out={pcm.as_posix()}'],cwd=R,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
  assert result.returncode==0,(O/f'render{style}.log').read_text()
 with ThreadPoolExecutor(max_workers=2)as pool:list(pool.map(render,[0,1]))
 for style,name in [(0,'空灵手碟'),(1,'律动手碟')]:
  pcm=O/f'style{style}.txt'
  values=np.loadtxt(pcm,dtype=np.int16);assert len(values)==384000
  previous=R/'build/handpan_trial_20261102/dual_write_reference'/f'style{style}.txt'
  if previous.exists():assert np.array_equal(values,np.loadtxt(previous,dtype=np.int16)),'Single-port optimization changed audible PCM'
  # Apply only the actual product's fixed scale (engine /4, nominal master x4).
  path=R/'output/handpan_trial_20261102'/f'{name}_RTL试听.wav';path.parent.mkdir(parents=True,exist_ok=True)
  with wave.open(str(path),'wb')as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000);f.writeframes(values.astype('<i2').tobytes())
  subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(path),'-b:a','192k',str(path.with_suffix('.mp3'))],check=True)
  assert np.max(np.abs(values.astype(np.int32)))<32767,'clipped audition'
  # First isolated C3 note: strongest modal peaks must be at 1f/2f/3f.
  x=values[200:12000].astype(float);nfft=131072;spectrum=np.abs(np.fft.rfft(x*np.hanning(len(x)),nfft))
  peaks=[]
  for harmonic in [1,2,3]:
   expected=130.81278265*harmonic;i=round(expected*nfft/48000);lo=max(0,i-8);hi=i+9
   found=(lo+int(np.argmax(spectrum[lo:hi])))*48000/nfft
   assert abs(found-expected)<1.2,(harmonic,found,expected);peaks.append(found)
  rows.append(dict(style=name,samples=len(values),peak=int(np.max(np.abs(values.astype(np.int32)))),modal_hz=peaks,pcm_source='actual Verilog simulation'))
  print(name,rows[-1],flush=True)
 (O/'pcm_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
