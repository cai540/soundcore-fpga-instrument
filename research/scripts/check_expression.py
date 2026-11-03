from pathlib import Path
import argparse,csv,json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/expression_20261028';OUT.mkdir(exist_ok=True)
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+');args=parser.parse_args()
project=ROOT/'board/soundcore_headphone_60k.gprj'
sources=[str((project.parent/e.attrib['path']).resolve()) for e in ET.parse(project).findall('.//File')
    if e.attrib['type']=='file.verilog' and Path(e.attrib['path']).name not in
    ['soundcore_headphone_top.v','pressure_i2s_panel_oled_ble_experiment_top.v','audio_pll_12m288.v']]
sources += [str(ROOT/'rtl'/name) for name in ['pressure_expression32.v','expressive_texture.v']]
sources += [str(p) for p in (OUT/'baseline').glob('expression_legacy_*.v')]
sources += [str(OUT/'lut_lookup_trial/lut_expression_texture.v')]
tests={'tb_pressure_expression32':[],'tb_expression_bitexact':[],'tb_expression_synth':[],'tb_expression_isolation':[],'tb_expression_rom_equiv':[],
    'tb_expression_texture':[],'tb_expression_core':[],
    'tb_early_pressure_allocator':[],'tb_pressure_voice_release':[],
    'tb_realtime_voice_integration':[],'tb_panel_audio_integration':[],
    'tb_playable_synth32':[]}
selected=args.only or list(tests);assert not set(selected)-set(tests)
results=json.loads((OUT/'tests.json').read_text()) if args.only and (OUT/'tests.json').exists() else []
for name in selected:
    options=['-Ptb_panel_audio_integration.HEADPHONE_TEST=1','-Ptb_panel_audio_integration.EARLY_TEST=1'] if name=='tb_panel_audio_integration' else []
    output=OUT/(name+'.vvp')
    c=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s',name,*options,'-o',str(output),
        str(ROOT/'tb'/(name+'.v')),*sources],cwd=ROOT,capture_output=True,text=True)
    assert c.returncode==0,name+': '+c.stdout+c.stderr
    runtime=[]
    if name=='tb_expression_texture':
        table=OUT/'texture_levels_rom.csv'
        if table.exists():
            lines=table.read_text().splitlines(keepends=True)
            complete=[lines[0]]
            for i,line in enumerate(lines[1:]):
                fields=line.strip().split(',')
                if not line.endswith('\n') or len(fields)!=6:break
                kind,n,a=i//315,(i%315)//9,i%9
                if [int(x) for x in fields[:3]]!=[kind,n,255 if a==8 else a*32]:break
                complete.append(line)
            table.write_text(''.join(complete));runtime=['+START='+str(len(complete)-1)]
    run=subprocess.run([str(TOOL/'vvp.exe'),str(output),*runtime],cwd=ROOT,capture_output=True,text=True,timeout=900)
    text=c.stdout+c.stderr+run.stdout+run.stderr;(OUT/(name+'.log')).write_text(text)
    passed=run.returncode==0 and 'PASS:' in text and 'FATAL:' not in text
    results=[r for r in results if r['test']!=name]+[dict(test=name,passed=passed,output=run.stdout.strip())]
    (OUT/'tests.json').write_text(json.dumps(results,indent=2))
    print(name,run.stdout.strip(),flush=True)
    if not passed:sys.exit(1)
assert all(r['passed'] for r in results)
print('PASS:',len(results),'expression checks; synthetic inputs, no hardware validation')
