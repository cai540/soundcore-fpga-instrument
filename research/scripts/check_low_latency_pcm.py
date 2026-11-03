"""Compare actual current PCM with frozen 7B69. No hardware writes."""
from pathlib import Path
import os,subprocess,json
R=Path(__file__).resolve().parents[1];O=R/'build/low_latency_20261101/pcm';O.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(R/'tmp'),TMP=str(R/'tmp'))
refs=[]
for name in ['poly_synth32_tm','synth_voice']:
    body=(R/'build/natural_seven_20261101/src/rtl'/(name+'.v')).read_text(encoding='utf8')
    body=body.replace('module '+name,'module reference_'+name,1)
    p=O/('reference_'+name+'.v');p.write_text(body,encoding='utf8');refs.append(p)
bin=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');vvp=O/'pcm.vvp'
c=subprocess.run([str(bin/'iverilog.exe'),'-g2012','-s','tb_low_latency_pcm','-o',str(vvp),
    str(R/'tb/tb_low_latency_pcm.v'),*map(str,refs),*map(str,(R/'rtl').glob('*.v'))],cwd=R,capture_output=True,text=True)
assert c.returncode==0,c.stderr
p=subprocess.run([str(bin/'vvp.exe'),str(vvp)],cwd=R,capture_output=True,text=True,timeout=240)
body=p.stdout+p.stderr;(O/'comparison.log').write_text(body,encoding='utf8')
assert p.returncode==0 and 'PASS:'in body,body
(O/'summary.json').write_text(json.dumps({'reference':'7B69','passed':True,'cases':12,'compared_frames':4560,
    'engines':['live 32-voice expressive','offline expressive'],'pitches':['C2','C4','C6'],
    'velocities':[72,220],'steady_and_release_pcm_bit_identical':True,'subjective_hardware_onset':'pending'},indent=2),encoding='utf8')
print(body)
