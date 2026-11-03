"""Exercise the integrated handpan engine and BLE selection from frozen B703 sources."""
from pathlib import Path
import subprocess,json,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]
B=R/'build/product_repair_20261103';T=B/'handpan';T.mkdir(exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
unused_tops={'pressure_i2s_panel_oled_ble_experiment_top.v','soundcore_melody_top.v','audio_pll_12m288.v'}
sources=[x.get('path') for x in ET.parse(B/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File') if x.get('type')=='file.verilog' and Path(x.get('path')).name not in unused_tops]
results=[]
for top in ['tb_handpan_control','tb_handpan_core']:
 binary=T/(top+'.vvp')
 built=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-I',str(B),'-s',top,'-o',str(binary),str(R/'tb'/(top+'.v')),*sources],cwd=R,capture_output=True,text=True)
 assert built.returncode==0,built.stderr
 ran=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=180)
 (T/(top+'.log')).write_text(ran.stdout+ran.stderr)
 assert ran.returncode==0 and 'PASS' in ran.stdout,ran.stdout+ran.stderr
 results.append(dict(test=top,passed=True));print(top,ran.stdout.strip(),flush=True)
(T/'results.json').write_text(json.dumps(results,indent=2))
