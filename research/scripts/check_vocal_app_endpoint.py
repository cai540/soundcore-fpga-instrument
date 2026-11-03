"""Replay actual new-App real-recording score bytes through existing FPGA RTL."""
from pathlib import Path
import subprocess,os,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/vocal_app_20261028'
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
template=(ROOT/'tb/tb_melody_upload_endpoint.v').read_text()
results=[]
for name in ['tigers','twinkle']:
 directory=OUT/'real_audio'/name
 prefix=directory.relative_to(ROOT).as_posix()
 code=template.replace('build/mono_recognition_20261028/fixtures',prefix).replace('notes!=12','notes!=`FIXTURE_NOTES')
 source=directory/'tb_vocal_endpoint.v';source.write_text(code)
 target=directory/'endpoint.vvp'
 c=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s','tb_melody_upload_endpoint','-o',str(target),str(source),
  *[str(ROOT/'rtl'/(m+'.v')) for m in ['uploaded_song_engine','ble_control_endpoint','ble_frame_parser']]],cwd=ROOT,capture_output=True,text=True)
 assert c.returncode==0,c.stdout+c.stderr
 r=subprocess.run([str(TOOL/'vvp.exe'),str(target)],cwd=ROOT,capture_output=True,text=True,timeout=60)
 text=c.stdout+c.stderr+r.stdout+r.stderr
 (directory/'endpoint.log').write_text(text)
 passed=r.returncode==0 and 'PASS:' in text and 'FATAL:' not in text
 results.append({'source':name,'passed':passed,'output':text.strip()});print(text.strip(),flush=True)
 assert passed
(OUT/'endpoint_validation.json').write_text(json.dumps(results,indent=2))
