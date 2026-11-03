"""Replay the real API result encoded by Android's ScoreTransfer through RTL."""
from pathlib import Path
import argparse, json, os, subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--fixture',type=Path,default=Path('build/score_api_20261030/android_fixture'))
OUT=(ROOT/p.parse_args().fixture).resolve()
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
assert (OUT/'android_upload.hex').exists(), 'Run Android ScoreApiTest first'
prefix=OUT.relative_to(ROOT).as_posix()
code=(ROOT/'tb/tb_melody_upload_endpoint.v').read_text().replace(
    'build/mono_recognition_20261028/fixtures',prefix).replace('notes!=12','notes!=`FIXTURE_NOTES')
source=OUT/'tb_score_api_endpoint.v';source.write_text(code)
target=OUT/'endpoint.vvp'
c=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s','tb_melody_upload_endpoint','-o',str(target),str(source),
    *[str(ROOT/'rtl'/(m+'.v')) for m in ['uploaded_song_engine','ble_control_endpoint','ble_frame_parser']]],
    cwd=ROOT,capture_output=True,text=True)
assert c.returncode==0,c.stdout+c.stderr
r=subprocess.run([str(TOOL/'vvp.exe'),str(target)],cwd=ROOT,capture_output=True,text=True,timeout=60)
output=c.stdout+c.stderr+r.stdout+r.stderr
(OUT/'endpoint.log').write_text(output)
passed=r.returncode==0 and 'PASS:' in output and 'FATAL:' not in output
(OUT/'validation.json').write_text(json.dumps({'passed':passed,'output':output.strip(),
    'physical_hardware_test':False},indent=2))
print(output.strip());assert passed
