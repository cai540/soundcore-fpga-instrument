from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json,wave,numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/handpan_rock_20261102/tests';O=R/'output/handpan_rock_20261102'
B.mkdir(parents=True,exist_ok=True);O.mkdir(parents=True,exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');binary=B/'render.vvp'
compiled=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s','tb_airy_metal_render','-o',str(binary),
 'tb/tb_airy_metal_render.v','rtl/handpan_modal32.v','rtl/note_step_table72.v','rtl/rock_voice_fx.v'],cwd=R,capture_output=True,text=True)
assert compiled.returncode==0,compiled.stderr
def render(style):
 with (B/f'render{style}.log').open('w',encoding='utf8')as log:
  result=subprocess.run([str(BIN/'vvp.exe'),str(binary),f'+style={style}',f'+out={(B/f"style{style}.txt").as_posix()}'],cwd=R,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 assert result.returncode==0,(B/f'render{style}.log').read_text()
with ThreadPoolExecutor(max_workers=2)as pool:list(pool.map(render,[0,1]))
rows=[]
for style,name in [(0,'空灵手碟'),(1,'金属电音_旋钮滑杆演示')]:
 values=np.loadtxt(B/f'style{style}.txt',dtype=np.int16);assert len(values)==384000
 peak=int(np.max(np.abs(values.astype(np.int32))));assert peak<32767
 if style:assert peak<=10501
 path=O/(name+'_RTL试听.wav')
 with wave.open(str(path),'wb')as f:
  f.setnchannels(1);f.setsampwidth(2);f.setframerate(48000);f.writeframes(values.astype('<i2').tobytes())
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(path),'-b:a','192k',str(path.with_suffix('.mp3'))],check=True)
 x=values[2400:14400].astype(float);power=np.abs(np.fft.rfft(x*np.hanning(len(x))))**2
 frequencies=np.fft.rfftfreq(len(x),1/48000)
 high=float(power[frequencies>130.8128*4].sum()/max(1,power.sum()))
 rows.append(dict(style=name,samples=len(values),peak=peak,rms=float(np.sqrt(np.mean(values.astype(float)**2))),upper_harmonic_fraction=high,source='actual Verilog simulation; no normalization or external effects'))
assert rows[1]['upper_harmonic_fraction']>rows[0]['upper_harmonic_fraction']+0.0001,'Metal voice did not gain distinct upper harmonics'
(B/'pcm_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(rows,ensure_ascii=False,indent=2))
