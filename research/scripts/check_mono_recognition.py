"""Bounded regression for runtime score transfer and unchanged product paths."""
from pathlib import Path
import os,subprocess,json,argparse,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/mono_recognition_20261028';OUT.mkdir(exist_ok=True)
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
p=argparse.ArgumentParser();p.add_argument('--only',nargs='+');args=p.parse_args()
tests={
 'tb_uploaded_song_engine':['uploaded_song_engine'],
 'tb_melody_upload_endpoint':['uploaded_song_engine','ble_control_endpoint','ble_frame_parser'],
 'tb_melody_product_integration':[],
 'tb_ble_frame_parser':['ble_frame_parser'],
 'tb_ble_realtime_endpoint':['ble_control_endpoint','ble_frame_parser'],
 'tb_ble_control_endpoint':['ble_control_endpoint','ble_frame_parser','front_panel_five_keys'],
 'tb_ble_extended_state':['ble_control_endpoint','ble_frame_parser'],
 'tb_ble_telemetry_scene':['ble_control_endpoint','ble_frame_parser','front_panel_five_keys'],
}
results=[]
for name,modules in tests.items():
 if args.only and name not in args.only:continue
 command=[str(TOOL/'iverilog.exe'),'-g2012','-s',name,'-o',str(OUT/(name+'.vvp')),
          str(ROOT/'tb'/(name+'.v'))]+[str(ROOT/'rtl'/(m+'.v')) for m in modules]
 if name=='tb_melody_product_integration':
  project=ET.parse(OUT/'gowin/soundcore_melody_60k.gprj')
  for x in project.findall('.//File'):
   if x.attrib.get('type')!='file.verilog' or Path(x.attrib['path']).name=='audio_pll_12m288.v':continue
   source=Path(x.attrib['path']);code=source.read_text(encoding='utf-8')
   # This Windows Icarus build rejects drive letters in `include paths.
   # Mirror only the directive for simulation; hardware sources stay intact.
   adapted=code.replace('`include "'+ROOT.as_posix()+'/','`include "')
   if adapted!=code:
    mirror=OUT/'sim_sources'/source.relative_to(ROOT);mirror.parent.mkdir(parents=True,exist_ok=True)
    mirror.write_text(adapted,encoding='utf-8');source=mirror
   command.append(str(source))
 c=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
 log=c.stdout+c.stderr
 if c.returncode:log+=f'\nCompiler exit: {c.returncode}\n'
 if c.returncode==0:
  r=subprocess.run([str(TOOL/'vvp.exe'),str(OUT/(name+'.vvp'))],capture_output=True,text=True,cwd=ROOT,timeout=180)
  log+=r.stdout+r.stderr;ok=r.returncode==0 and 'PASS:' in log and 'FATAL:' not in log
 else:ok=False
 (OUT/(name+'.log')).write_text(log,encoding='utf-8')
 results.append(dict(test=name,passed=ok,output=log.strip()))
 print(name,log.strip(),flush=True)
 if not ok:break
(OUT/'rtl_checks.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
assert len(results)==len([x for x in tests if not args.only or x in args.only]) and all(x['passed'] for x in results)
