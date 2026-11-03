"""Verify actual synthesis, frame deadlines and source-isolated preview captures."""
from pathlib import Path
import os,subprocess,json,argparse
R=Path(__file__).resolve().parents[1];B=R/'build/harmonica_refinement_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH'];os.environ['TEMP']=os.environ['TMP']=str(R/'tmp')
def run(name,bench,files,timeout=600):
    image=B/(name+'.vvp');c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',name,'-o',str(image),str(bench),*map(str,files)],cwd=R,capture_output=True,text=True)
    (B/(name+'_compile.log')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
    with(B/(name+'.log')).open('w')as f:p=subprocess.run([str(BIN/'vvp.exe'),str(image)],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    log=(B/(name+'.log')).read_text();assert p.returncode==0 and 'PASS:'in log and 'FATAL'not in log,log[-2500:]
    print(log.strip(),flush=True);return dict(test=name,passed=True,output=log)
def capture():
    old=(B/'baseline/rtl/synth_voice.v').read_text().replace('module synth_voice #(','module harmonica_baseline_voice #(').replace('expressive_texture #(','harmonica_baseline_texture #(')
    old=old.replace('"rtl/instrument_attack.vh"','"'+(B/'baseline/rtl/instrument_attack.vh').relative_to(R).as_posix()+'"')
    (B/'baseline_voice.v').write_text(old)
    old=(B/'baseline/rtl/expressive_texture.v').read_text().replace('module expressive_texture #(','module harmonica_baseline_texture #(')
    for name in ['expression_normalized.mem','expression_raw.mem']:old=old.replace((R/'rtl'/name).as_posix(),(B/'baseline/rtl'/name).as_posix())
    (B/'baseline_texture.v').write_text(old)
    files=[R/'rtl'/n for n in ['synth_voice.v','expressive_texture.v','instrument_texture.v','note_step_table72.v','song_event_player.v','pitch_layout.v']]+[B/'baseline_voice.v',B/'baseline_texture.v']
    return run('tb_harmonica_refinement_capture',R/'tb/tb_harmonica_refinement_capture.v',files,1200)
def regress():
    rtl=list((R/'rtl').glob('*.v'));results=[]
    # Retain all old onset invariants, changing only the intended full-body
    # deadline and allowing the longer breath rise before sustain assertions.
    s=(R/'tb/tb_low_latency_attack.v').read_text().replace('module tb_low_latency_attack;','module tb_harmonica_onset;')
    s=s.replace('n<800','n<1500').replace('(kind ? 128:256)','(kind ? 1152:256)').replace('repeat(600)','repeat(1300)').replace('repeat(650)','repeat(1300)')
    tb=B/'tb_harmonica_onset.v';tb.write_text(s);results.append(run('tb_harmonica_onset',tb,rtl))
    s=(R/'tb/tb_expression_synth.v').read_text().replace('module tb_expression_synth;','module tb_harmonica_voices;').replace('[191:0]','[223:0]').replace('i*6 +: 6','i*7 +: 7')
    tb=B/'tb_harmonica_voices.v';tb.write_text(s);results.append(run('tb_harmonica_voices',tb,rtl))
    for name in ['tb_synth_timbre_latch','tb_pressure_expression32','tb_ble_realtime_endpoint','tb_k5_lamp_follow']:
        if name=='tb_ble_realtime_endpoint':continue # covered by complete previous product; no transport edits here
        s=(R/'tb'/(name+'.v')).read_text().replace(".timbre(1'b1)",".timbre(2'd1)")if name=='tb_k5_lamp_follow'else(R/'tb'/(name+'.v')).read_text()
        tb=B/(name+'.v');tb.write_text(s);results.append(run(name,tb,rtl))
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',action='store_true');a=p.parse_args()
    results=[capture()]if a.capture else regress();(B/('capture_results.json'if a.capture else'regression_results.json')).write_text(json.dumps(results,indent=2))
