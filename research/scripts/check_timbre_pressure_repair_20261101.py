"""Check the frozen candidate, keeping all older regression artifacts intact."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/timbre_pressure_repair_20261101'
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
parser=argparse.ArgumentParser();parser.add_argument('--audition',action='store_true');parser.add_argument('--spectral',action='store_true');parser.add_argument('--only',nargs='+');args=parser.parse_args()
sources=[Path(x.attrib['path']) for x in ET.parse(OUT/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File') if x.attrib['type']=='file.verilog']
sources=[p for p in sources if p.name not in ['audio_pll_12m288.v','soundcore_melody_top.v','pressure_i2s_panel_oled_ble_experiment_top.v']]
def run(name,bench,files=None,options=(),timeout=240):
    binary=OUT/(name+'.vvp');result=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s',name,*options,'-o',str(binary),str(bench),*map(str,files or sources)],cwd=ROOT,capture_output=True,text=True)
    log=result.stdout+result.stderr
    (OUT/(name+'_compile.json')).write_text(json.dumps({'returncode':result.returncode,'output':log},indent=2),encoding='utf-8')
    assert result.returncode==0,f'{name} compiler exit {result.returncode}: '+log[-3000:]
    result=subprocess.run([str(TOOL/'vvp.exe'),str(binary)],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    log+=result.stdout+result.stderr;(OUT/(name+'.log')).write_text(log,encoding='utf-8')
    passed=result.returncode==0 and 'PASS' in log and 'FATAL' not in log
    print(name,result.stdout.strip(),flush=True);assert passed,name
    return {'test':name,'passed':True,'output':result.stdout.strip()}

if args.audition:
    before=OUT/'before'
    voice=(OUT/'src/rtl/synth_voice.v').read_text(encoding='utf-8')
    (before/'repair_old_synth_voice.v').write_text(voice.replace('module synth_voice #(','module repair_old_synth_voice #(').replace('expressive_texture #(','repair_old_expressive_texture #('),encoding='utf-8')
    (OUT/'repair_tonal_synth_voice.v').write_text(voice.replace('module synth_voice #(','module repair_tonal_synth_voice #(').replace('expressive_texture #(','repair_tonal_expressive_texture #('),encoding='utf-8')
    texture=(OUT/'src/rtl/expressive_texture.v').read_text(encoding='utf-8')
    (OUT/'repair_tonal_expressive_texture.v').write_text(texture.replace('module expressive_texture #(','module repair_tonal_expressive_texture #(').replace('parameter integer NOISE_ENABLE=1','parameter integer NOISE_ENABLE=0'),encoding='utf-8')
    selected=[OUT/'src/rtl'/p for p in ['synth_voice.v','instrument_texture.v','expressive_texture.v','pressure_expression32.v','note_step_table35.v']]
    selected += [before/'repair_old_synth_voice.v',before/'repair_old_expressive_texture.v',OUT/'repair_tonal_synth_voice.v',OUT/'repair_tonal_expressive_texture.v']
    results=[run('tb_timbre_repair_audition',ROOT/'tb/tb_timbre_repair_audition.v',selected,timeout=900)]
    target='audition_tests.json'
elif args.spectral:
    bench=OUT/'tb_expression_texture.v'
    bench.write_text((ROOT/'tb/tb_expression_texture.v').read_text(encoding='utf-8').replace('build/expression_20261028/texture_levels_rom.csv','build/timbre_pressure_repair_20261101/texture_levels.csv'),encoding='utf-8')
    results=[run('tb_expression_texture',bench,timeout=900)];target='spectral_tests.json'
else:
    selected=['tb_pressure_repair_profile','tb_seven_pad_repair_core','tb_expression_synth','tb_expression_isolation',
        'tb_pressure_expression32','tb_early_pressure_allocator','tb_playable_synth32','tb_realtime_voice_integration',
        'tb_pressure_voice_release','tb_native_demo_audio','tb_k5_lamp_follow','tb_i2s_stereo_tx',
        'tb_shared_pitch_snapshot','tb_shared_pitch_equivalence']
    if args.only:selected=[name for name in selected if name in args.only]
    results=[]
    if args.only:
        for saved in ['tests.json','tests_partial.json']:
            if (OUT/saved).exists():
                for item in json.loads((OUT/saved).read_text(encoding='utf-8')):
                    results=[r for r in results if r['test']!=item['test']]+[item]
    for name in selected:
        bench=ROOT/'tb'/(name+'.v')
        if name=='tb_early_pressure_allocator':
            text=bench.read_text(encoding='utf-8').replace('voice_velocity[k*8 +: 8]!=30',
                'voice_velocity[k*8 +: 8]!=(notes[k*6 +: 6]==34 ? 35 : 30)').replace(
                'voice_velocity[k*8 +: 8]!=212','voice_velocity[k*8 +: 8]!=(j==6 ? 255 : 212)').replace(
                'seven early voices corrected30->212','six voices30->212, calibrated AI6 35->255, corrected')
            bench=OUT/'tb_early_pressure_allocator.v';bench.write_text(text,encoding='utf-8')
        extra=sources+[ROOT/'build/shared_pitch_20261028/baseline/playable_synth32_legacy.v'] if name.startswith('tb_shared_pitch_') else None
        result=run(name,bench,files=extra)
        results=[r for r in results if r['test']!=name]+[result]
        (OUT/'tests_partial.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    # Same actual MAX stereo receiver used in the prior speaker regression.
    bench=ROOT/'build/speaker_led_pressure_calibrated_20261031/simulation/tb_expression_speaker_core.v'
    assert bench.exists()
    if not args.only or 'tb_expression_speaker_core' in args.only:results.append(run('tb_expression_speaker_core',bench))
    target='tests.json'
(OUT/target).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
frozen=json.loads((OUT/'frozen_inputs.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((OUT/'src'/name).read_bytes()).hexdigest()==digest for name,digest in frozen.items())
print('Frozen source hashes verified; no hardware programming',flush=True)
