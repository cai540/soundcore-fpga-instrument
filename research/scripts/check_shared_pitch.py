"""Freeze a legacy reference and check the shared wrapper, without hardware."""
from pathlib import Path
import argparse,hashlib,json,math,os,shutil,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/shared_pitch_20261028';OUT.mkdir(parents=True,exist_ok=True)
BASE=OUT/'baseline';BASE.mkdir(exist_ok=True)
TOOLS=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['snapshot','directed','all'],default='all')
parser.add_argument('--only',nargs='+');parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
project=ROOT/'board/soundcore_headphone_60k.gprj'
inputs=[project]+[(project.parent/e.attrib['path']).resolve() for e in ET.parse(project).findall('.//File')]
manifest=BASE/'source_sha256.json'
if not manifest.exists():
    release=json.loads((ROOT/'build/headphone_20261027/release.json').read_text())
    baseline_release=next(x for x in release['firmware'] if 'soundcore_headphone_' in x['firmware'])
    for rel,expected in baseline_release['inputs_sha256'].items():
        assert sha(ROOT/rel)==expected,'Refuse to capture a changed product as baseline: '+rel
    hashes={}
    for p in inputs:
        dst=BASE/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
        hashes[str(p.relative_to(ROOT))]=sha(p)
    protected=json.loads((ROOT/'build/headphone_20261027/protected.json').read_text())
    for rel,expected in protected.items():assert sha(ROOT/rel)==expected,'Protected input drift: '+rel
    (BASE/'protected.json').write_text(json.dumps(protected,indent=2),encoding='utf-8')
    manifest.write_text(json.dumps(hashes,indent=2),encoding='utf-8')
for rel,expected in json.loads(manifest.read_text()).items():
    assert sha(BASE/rel)==expected,'Frozen reference changed: '+rel
legacy=BASE/'playable_synth32_legacy.v'
if not legacy.exists():
    legacy.write_text((BASE/'rtl/playable_synth32.v').read_text().replace('module playable_synth32 (','module playable_synth32_legacy ('),encoding='utf-8')
assert legacy.read_text()==(BASE/'rtl/playable_synth32.v').read_text().replace('module playable_synth32 (','module playable_synth32_legacy ('),'Legacy comparison module drift'
oracle=[]
for bend in range(256):
    for note in range(64):
        base=round(440*2**((60+note-69)/12)*2**32/48000) if note<35 else 0
        oracle.append(f'{((base*(65536+(bend-128)*30))>>16)&0xffffffff:08x}')
(OUT/'pitch_oracle.mem').write_text('\n'.join(oracle)+'\n')
sources=[str(p) for p in inputs[1:] if p.suffix=='.v' and p.name not in
         ['pressure_i2s_panel_oled_ble_experiment_top.v','soundcore_headphone_top.v','audio_pll_12m288.v']]
if args.baseline:
    sources=[str(BASE/'rtl/playable_synth32.v') if Path(p).name=='playable_synth32.v' else p for p in sources]
directed=['tb_shared_pitch_snapshot','tb_shared_pitch_equivalence']
existing=['tb_playable_synth32','tb_poly_synth32_tm','tb_poly_erhu_expression',
          'tb_pressure_i2s_poly32_core','tb_remote_physical_polyphony','tb_realtime_voice_integration',
          'tb_panel_audio_integration','tb_pressure_voice_release',
          'tb_pt8211_tx_12m288']
tests=directed[:1] if args.phase=='snapshot' else directed if args.phase=='directed' else directed+existing
if args.only:
    assert not set(args.only)-set(directed+existing),'Unknown test'
    tests=args.only
result_file=OUT/(('baseline_' if args.baseline else '')+args.phase+'_tests.json')
results=json.loads(result_file.read_text()) if args.only and result_file.exists() else []
for name in tests:
    options=['-Ptb_panel_audio_integration.HEADPHONE_TEST=1'] if name=='tb_panel_audio_integration' else []
    stem=('baseline_' if args.baseline else '')+name
    out=OUT/(stem+'.vvp')
    extra=[str(ROOT/'board/pressure_i2s_poly32_core.v')] if name=='tb_pressure_i2s_poly32_core' else []
    command=[str(TOOLS/'iverilog.exe'),'-g2012','-s',name,*options,'-o',str(out),str(ROOT/'tb'/(name+'.v')),*sources,*extra,str(legacy)]
    c=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    if c.returncode:
        (OUT/(stem+'_compile_failure.json')).write_text(json.dumps({'returncode':c.returncode,'command':command,'stdout':c.stdout,'stderr':c.stderr},indent=2),encoding='utf-8')
        raise RuntimeError(f'{name} compilation exited {c.returncode}: '+c.stdout+c.stderr)
    r=subprocess.run([str(TOOLS/'vvp.exe'),str(out)],cwd=ROOT,capture_output=True,text=True)
    output=c.stdout+c.stderr+r.stdout+r.stderr
    (OUT/(stem+'.log')).write_text(output,encoding='utf-8')
    passed=r.returncode==0 and 'PASS:' in output and 'FATAL:' not in output
    results=[x for x in results if x['test']!=name]
    results.append({'test':name,'passed':passed,'output':r.stdout.strip()})
    result_file.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(name,output.strip(),flush=True)
    if not passed:sys.exit(1)
assert all(x['passed'] for x in results),'An earlier test in this result set is still failing'
print('PASS:',len(results),'shared-pitch and integration checks',flush=True)
