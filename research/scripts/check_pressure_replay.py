"""Synthetic saved-trace fixture and negative CSV checks; not real sensor data."""
from pathlib import Path
import csv,json,subprocess,sys
from replay_pressure_trace import ROOT,load_trace,replay
OUT=ROOT/'build/early_pressure_20261028/replay';OUT.mkdir(exist_ok=True)
profile=json.loads((ROOT/'config/pressure_profile_v1.json').read_text(encoding='utf-8'))
shapes={'plateau':[800]*5,'ramp':[300,450,650,900,1100],
        'decay':[900,880,860,840,820],'spike':[900,0,0,0,0],
        'late_peak':[600,600,600,1100,1050],'low_margin':[300]*5}
summary=[];combined=[]
for name,shape in shapes.items():
    rows=[];clock=0
    for sweep in range(16+5+40):
        exc=shape[sweep-16] if 16<=sweep<21 else 0
        for ch in range(8):
            rows.append(dict(clock=clock,channel=ch,adc=1000+exc if ch<7 else 2048,
                trigger=int(sweep==16 and ch==0)));clock+=400
    path=OUT/(name+'_SYNTHETIC.csv')
    for row in rows:combined.append({**row,'clock':len(combined)*400,'elapsed_clock':len(combined)*400})
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['clock','channel','adc','trigger']);w.writeheader();w.writerows(rows)
    report=OUT/(name+'_replay.json')
    subprocess.run([sys.executable,str(ROOT/'scripts/replay_pressure_trace.py'),str(path),'--output',str(report),'--synthetic'],check=True,capture_output=True)
    r=json.loads(report.read_text(encoding='utf-8'));assert r['legacy_note_count']==r['candidate_note_count']==7
    expect_early=name in ('plateau','decay','late_peak')
    assert r['early_count']==(7 if expect_early else 0)
    for c in r['comparisons']:assert c['saved_clocks']==(6400 if expect_early else 0)
    if name=='late_peak':
        for ch in range(7):
            correction=[e['level'] for e in r['candidate_events'] if e['channel']==ch and e['level'] is not None]
            expected=next(c['old_velocity'] for c in r['comparisons'] if c['channel']==ch)
            assert expected in correction
    summary.append({'shape':name,'notes':7,'early':r['early_count'],'synthetic':True})
# Feed the exact saved traces and model outputs into a separate RTL replay.
events={r['elapsed_clock']:r for r in replay(combined,profile,True)}
inputs=[];expected=[]
for r in combined:
    inputs.append(f"{(r['channel']<<12)|r['adc']:04x}")
    e=events.get(r['elapsed_clock'],{});fire=e.get('strike') is not None;lv=e.get('level') is not None
    packed=(int(fire)<<18)|((e.get('strike') or 0)<<10)|(int(e.get('strike_early',False))<<9)|(int(lv)<<8)|(e.get('level') or 0)
    expected.append(f'{packed:05x}')
assert len(inputs)==2928
(OUT/'input.mem').write_text('\n'.join(inputs)+'\n')
(OUT/'expected.mem').write_text('\n'.join(expected)+'\n')
# Reject malformed files and ambiguous backward/duplicate timestamps.
for text in ['clock,channel,adc\n0,0,4096\n','clock,channel,adc\n0,8,10\n',
             'clock,channel,adc\n10,0,10\n10,1,10\n','clock,channel,adc\n10,0,10\n9,1,10\n']:
    bad=OUT/'invalid.csv';bad.write_text(text)
    try:load_trace(bad)
    except ValueError:pass
    else:raise AssertionError('invalid trace accepted')
bad.unlink()
wrap=OUT/'wrap.csv';wrap.write_text('clock,channel,adc\n4294967290,0,1000\n3,1,1000\n')
assert load_trace(wrap)[1]['elapsed_clock']==9;wrap.unlink()
try:replay([{'channel':0,'adc':1000,'clock':0}],profile,True)
except ValueError:pass
else:raise AssertionError('insufficient automatic zero samples accepted')
(OUT/'checks.json').write_text(json.dumps({'passed':True,'fixtures':summary,'malformed_cases':4,
    'timestamp_wrap':True,'insufficient_startup_rejected':True,'evidence_kind':'synthetic'},indent=2))
print('PASS: six saved/reloaded synthetic CSV shapes, 42 notes, malformed input rejection and clock wrap; not empirical evidence')
