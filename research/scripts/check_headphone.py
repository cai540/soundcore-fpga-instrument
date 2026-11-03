"""Exercise serial words and the real sensor/core headphone path; no hardware access."""
from pathlib import Path
import json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/headphone_20261027'
TOOLS=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
sources=[str((ROOT/'board'/e.attrib['path']).resolve().relative_to(ROOT))
    for e in ET.parse(ROOT/'board/soundcore_headphone_60k.gprj').findall('.//File')
    if e.attrib['type']=='file.verilog' and e.attrib['path'] not in
        ('pressure_i2s_panel_oled_ble_experiment_top.v','soundcore_headphone_top.v','audio_pll_12m288.v')]
cases=[('tb_pt8211_tx_12m288',[],[]),('tb_headphone_check',[],['board/headphone_check_top.v']),
       ('tb_panel_audio_integration',['-Ptb_panel_audio_integration.HEADPHONE_TEST=1'],[]),
       ('tb_pt8211_tx',[],['rtl/pt8211_tx.v'])]
results=[]
for name,options,extra in cases:
    image=OUT/(name+'.vvp')
    comp=subprocess.run([str(TOOLS/'iverilog.exe'),'-g2012','-s',name,*options,'-o',str(image),
                         'tb/'+name+'.v',*sources,*extra],cwd=ROOT,capture_output=True,text=True)
    if comp.returncode:raise RuntimeError(comp.stdout+comp.stderr)
    run=subprocess.run([str(TOOLS/'vvp.exe'),str(image)],cwd=ROOT,capture_output=True,text=True)
    output=comp.stdout+comp.stderr+run.stdout+run.stderr
    (OUT/(name+'.log')).write_text(output,encoding='utf-8')
    passed=run.returncode==0 and 'PASS:' in output and 'FATAL:' not in output
    results.append(dict(test=name,passed=passed))
    (OUT/'headphone_tests.json').write_text(json.dumps(results,indent=2)+'\n')
    print(name,output,flush=True)
    if not passed:sys.exit(1)
