"""Run real audio-path regressions and record the source used by each test."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',default='build/onset_20261027');parser.add_argument('--texture',action='store_true');args=parser.parse_args()
OUT=ROOT/args.out;OUT.mkdir(parents=True,exist_ok=True)
TOOLS=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
sources=[str((ROOT/'board'/e.attrib['path']).resolve().relative_to(ROOT))
    for e in ET.parse(ROOT/'board/pressure_i2s_panel_oled_ble_experiment_60k.gprj').findall('.//File')
    if e.attrib['type']=='file.verilog' and e.attrib['path'] not in
        ('pressure_i2s_panel_oled_ble_experiment_top.v','audio_pll_12m288.v')]
tests=['tb_instrument_onset','tb_poly_synth32_tm','tb_poly_erhu_expression',
       'tb_synth_timbre_latch','tb_pressure_voice_release',
       'tb_strike_voice_allocator32_banked','tb_realtime_voice_integration',
       'tb_panel_audio_integration','tb_song_word_articulation']
if args.texture:tests.insert(0,'tb_instrument_texture')
results=[]
for name in tests:
    image=OUT/(name+'.vvp')
    compile=subprocess.run([str(TOOLS/'iverilog.exe'),'-g2012','-s',name,'-o',str(image),
        str(ROOT/'tb'/(name+'.v')),*sources],cwd=ROOT,capture_output=True,text=True)
    if compile.returncode:raise RuntimeError(compile.stdout+compile.stderr)
    run=subprocess.run([str(TOOLS/'vvp.exe'),str(image)],cwd=ROOT,capture_output=True,text=True)
    text=compile.stdout+compile.stderr+run.stdout+run.stderr
    (OUT/(name+'.log')).write_text(text,encoding='utf-8')
    passed=run.returncode==0 and 'PASS:' in text and 'FATAL:' not in text
    results.append(dict(test=name,passed=passed))
    (OUT/'regression.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(name,run.returncode,text.strip(),flush=True)
    if not passed:sys.exit(1)
print('PASS: all',len(tests),'audio-path regression checks',flush=True)
