"""Affected-feature checks on the exact frozen B713 inputs. No hardware calls."""
from pathlib import Path
import json,subprocess,xml.etree.ElementTree as ET,os,re
from simulation_sources import iverilog_sources
R=Path(__file__).resolve().parents[1];B=R/'build/contest_audit_20261103/firmware';O=B.parent/'rtl_checks';O.mkdir(exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
files=[Path(x.get('path'))for x in ET.parse(B/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')if x.get('type')=='file.verilog' and Path(x.get('path')).name not in ('audio_pll_12m288.v','soundcore_melody_top.v')]
files=iverilog_sources(files,O/'sources',R);results=[]
# Expand Verilog net-initializer sugar for Icarus's forward-reference binder.
# `wire x = expression` and `wire x; assign x = expression` are identical nets.
top=next(p for p in files if p.name.endswith('_pressure_i2s_panel_oled_ble_experiment_top.v'))
body=top.read_text(encoding='utf8')
def explicit_assign(match):
 declaration=match[1].strip();name=re.search(r'(\w+)$',declaration)[1]
 return '    '+declaration+';\n    assign '+name+' = '+match[2]+';'
body=re.sub(r'(?m)^    (wire\b[^;\n=]+?)\s*=\s*([^;]+);',explicit_assign,body)
declarations=re.findall(r'(?m)^    wire\b[^;]+;\n',body)
body=re.sub(r'(?m)^    wire\b[^;]+;\n','',body)
at=body.index('\n);')+len('\n);\n')
body=body[:at]+''.join(declarations)+body[at:]
top.write_text(body,encoding='utf8')
(O/'icarus_compatibility.json').write_text(json.dumps(dict(include_path_spelling_only=True,
 top_net_initializers_expanded_to_continuous_assign=True,top_wire_declarations_first=True,expressions_changed=False,uses_vendor_ram_models=True,
 physical_hardware_test=False),indent=2),encoding='utf8')
vendor=Path('D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
assert vendor.is_file()
files.append(vendor) # Real vendor DPB/DPX9B simulation models, not empty RAM stubs.
for name in ('tb_guide_rhythm_cue','tb_product_adsr','tb_contest_guide_top','tb_tools_protocol','tb_tools_bulk_endpoint','tb_handpan_control','tb_handpan_core'):
 executable=O/(name+'.vvp')
 compile=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-I',str(B),'-s',name,'-o',str(executable),str(R/'tb'/(name+'.v')),*map(str,files)],cwd=R,capture_output=True,text=True)
 (O/(name+'_compile.log')).write_text(compile.stdout+compile.stderr,encoding='utf8');assert compile.returncode==0,compile.stderr
 run=subprocess.run([str(BIN/'vvp.exe'),str(executable)],cwd=R,capture_output=True,text=True,timeout=240)
 (O/(name+'.log')).write_text(run.stdout+run.stderr,encoding='utf8')
 passed=run.returncode==0 and 'PASS' in run.stdout
 results.append(dict(test=name,passed=passed,source='frozen B713; simulation only'))
 print(name,passed,flush=True)
 assert passed,run.stdout+run.stderr
(O/'results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
