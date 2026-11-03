from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/early_pressure_20261028';OUT.mkdir(exist_ok=True)
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+');args=parser.parse_args()
legacy=OUT/'baseline/fsr_strike_detector_legacy.v'
project=ROOT/'board/soundcore_headphone_60k.gprj'
sources=[str((project.parent/e.attrib['path']).resolve()) for e in ET.parse(project).findall('.//File')
         if e.attrib['type']=='file.verilog' and Path(e.attrib['path']).name not in
         ['soundcore_headphone_top.v','pressure_i2s_panel_oled_ble_experiment_top.v','audio_pll_12m288.v']]
tests={'tb_pressure_saved_profile':[],'tb_early_pressure_detector':[],
       'tb_pressure_trace_replay':[],'tb_early_pressure_allocator':[],
       'tb_fsr_trace_capture':[str(ROOT/'rtl/fsr_trace_capture.v')],
       'tb_fsr_strike_detector':[],'tb_panel_audio_integration':[],
       'tb_panel_audio_integration_default':[],
       'tb_realtime_voice_integration':[],'tb_pressure_voice_release':[]}
selected=args.only or list(tests)
assert not set(selected)-set(tests)
results=json.loads((OUT/'tests.json').read_text()) if args.only and (OUT/'tests.json').exists() else []
for name in selected:
    top='tb_panel_audio_integration' if name=='tb_panel_audio_integration_default' else name
    options=['-Ptb_panel_audio_integration.HEADPHONE_TEST=1',
             '-Ptb_panel_audio_integration.EARLY_TEST='+str(int(name!='tb_panel_audio_integration_default'))] if top=='tb_panel_audio_integration' else []
    target=OUT/(name+'.vvp')
    cmd=[str(TOOL/'iverilog.exe'),'-g2012','-s',top,*options,'-o',str(target),str(ROOT/'tb'/(top+'.v')),*sources,str(legacy),*tests[name]]
    c=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    assert c.returncode==0,f'{name} compilation failed {c.returncode}: {c.stdout}{c.stderr}'
    r=subprocess.run([str(TOOL/'vvp.exe'),str(target)],cwd=ROOT,capture_output=True,text=True)
    text=c.stdout+c.stderr+r.stdout+r.stderr;(OUT/(name+'.log')).write_text(text,encoding='utf-8')
    passed=r.returncode==0 and 'PASS:' in text and 'FATAL:' not in text
    results=[x for x in results if x['test']!=name]+[{'test':name,'passed':passed,'output':r.stdout.strip()}]
    (OUT/'tests.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(name,text.strip(),flush=True)
    if not passed:sys.exit(1)
assert all(x['passed'] for x in results)
print('PASS:',len(results),'persistent/early pressure checks; synthetic evidence only')
