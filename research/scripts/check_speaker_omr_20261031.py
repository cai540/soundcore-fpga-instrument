"""Verify standard I2S and the saved full pressure/expression path before programming."""
from pathlib import Path
import argparse,json,os,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--build-dir',default='build/speaker_omr_20261031')
parser.add_argument('--pressure-regression',action='store_true')
parser.add_argument('--only',nargs='+')
args=parser.parse_args()
OUT=ROOT/args.build_dir;SIM=OUT/'simulation';SIM.mkdir(exist_ok=True)
metadata=json.loads((OUT/'build_metadata.json').read_text(encoding='utf-8'))
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
old=(ROOT/'tb/tb_expression_core.v').read_text(encoding='utf-8')
start=old.index('    always @(posedge dut.sample_tick)')
end=old.index('    pressure_i2s_additive32_core',start)
receiver='''    always @(posedge dut.sample_tick)if(rst_n)begin ready=1;bits=0;end
    always @(posedge bck)if(rst_n && ready)begin
        if(ws!==(bits>=32))$fatal(1,"speaker I2S WS mismatch");
        if(bits==1)begin expected=dut.output_sample;decoded=0;end
        if(bits==33)decoded=0;
        if((bits>=1&&bits<=16)||(bits>=33&&bits<=48))begin
            decoded={decoded[14:0],din};
            if(bits==16||bits==48)begin
                if(decoded!==expected)$fatal(1,"speaker I2S sample mismatch");words=words+1;
            end
        end else if(din!==0)$fatal(1,"I2S padding bit was not zero");
        bits=bits+1;
    end
'''
new=(old[:start]+receiver+old[end:]).replace('module tb_expression_core','module tb_expression_speaker_core').replace('.HEADPHONE_OUTPUT(1)','.HEADPHONE_OUTPUT(0)').replace('headphone','speaker I2S')
test=SIM/'tb_expression_speaker_core.v';test.write_text(new,encoding='utf-8')
files=[Path(i.attrib['path'])for i in ET.parse(OUT/'soundcore_speaker_omr_60k.gprj').findall('./FileList/File')if i.attrib['type']=='file.verilog']
files=[p for p in files if p.name not in ['audio_pll_12m288.v','soundcore_melody_top.v','pressure_i2s_panel_oled_ble_experiment_top.v']]
checks=[('tb_i2s_stereo_tx',ROOT/'tb/tb_i2s_stereo_tx.v',[]),
        ('tb_expression_speaker_core',test,[]),
        ('tb_panel_audio_integration',ROOT/'tb/tb_panel_audio_integration.v',['-Ptb_panel_audio_integration.HEADPHONE_TEST=0','-Ptb_panel_audio_integration.EARLY_TEST=1']),
        ('tb_playable_synth32',ROOT/'tb/tb_playable_synth32.v',[])]
if args.pressure_regression:
    checks.extend([('tb_seven_pad_full_scale',ROOT/'tb/tb_seven_pad_full_scale.v',[]),
                   ('tb_pressure_expression32',ROOT/'tb/tb_pressure_expression32.v',[]),
                   ('tb_pressure_saved_profile',ROOT/'tb/tb_pressure_saved_profile.v',[])])
    if metadata.get('calibrated_input_scale_q12'):
        checks[-3]=('tb_seven_pad_full_scale',ROOT/'tb/tb_seven_pad_full_scale.v',['-Ptb_seven_pad_full_scale.CALIBRATED_TEST=1'])
        checks[-1]=('tb_pressure_calibrated_profile',ROOT/'tb/tb_pressure_calibrated_profile.v',[])
if args.only:
    assert not set(args.only)-{x[0]for x in checks}
    checks=[x for x in checks if x[0]in args.only]
results=json.loads((OUT/'tests.json').read_text(encoding='utf-8')) if args.only and (OUT/'tests.json').exists() else []
for top,bench,options in checks:
    image=SIM/(top+'.vvp')
    extra=[ROOT/'build/early_pressure_20261028/baseline/fsr_strike_detector_legacy.v'] if top=='tb_pressure_saved_profile' else []
    c=subprocess.run([str(TOOL/'iverilog.exe'),'-g2012','-s',top,*options,'-o',str(image),str(bench),*map(str,files+extra)],cwd=ROOT,capture_output=True,text=True)
    log=c.stdout+c.stderr
    (SIM/(top+'.log')).write_text(log,encoding='utf-8')
    assert c.returncode==0,f'{top} compile exit {c.returncode}: '+log[-2000:]
    r=subprocess.run([str(TOOL/'vvp.exe'),str(image)],cwd=ROOT,capture_output=True,text=True,timeout=240)
    log+=r.stdout+r.stderr;(SIM/(top+'.log')).write_text(log,encoding='utf-8')
    passed=r.returncode==0 and 'PASS'in r.stdout and 'FATAL'not in log
    results=[x for x in results if x['test']!=top]+[{'test':top,'passed':passed,'output':r.stdout.strip()}]
    (OUT/'tests.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(top,r.stdout.strip(),flush=True);assert passed,top+' failed'
print(f'PASS: {len(checks)} selected RTL checks; {len(results)} stored results for {OUT.name}')
