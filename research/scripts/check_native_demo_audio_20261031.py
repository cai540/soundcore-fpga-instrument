"""Check the new native entry through actual synthesized speaker PCM."""
from pathlib import Path
import json,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/native_panel_playback_20261031'
test='tb_native_demo_audio';binary=OUT/'simulation'/(test+'.vvp')
files=[node.attrib['path'] for node in ET.parse(OUT/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')
    if node.attrib['path'].endswith('.v') and (Path(node.attrib['path']).parent.name=='rtl' or
        Path(node.attrib['path']).name=='pressure_i2s_additive32_core.v')]
c=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012','-s',test,'-o',str(binary),str(ROOT/'tb'/(test+'.v')),*files],capture_output=True,text=True,cwd=ROOT)
assert c.returncode==0,(c.stdout,c.stderr)
r=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe',str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=150)
body=r.stdout+r.stderr;passed=r.returncode==0 and 'PASS:'in body
(OUT/'simulation'/(test+'.log')).write_text(body,encoding='utf-8')
p=OUT/'panel_menu_tests.json';tests=json.loads(p.read_text(encoding='utf-8'))
tests=[t for t in tests if t['test']!=test]+[{'test':test,'passed':passed,'output':body}]
p.write_text(json.dumps(tests,ensure_ascii=False,indent=2),encoding='utf-8')
print(body,flush=True)
assert passed,test
