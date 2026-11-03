"""Validate and replay saved ADC CSV. No fitting, no invented empirical data.

CSV columns: clock,channel,adc,trigger(optional). Clock is a 32-bit FPGA
counter; one wrap is allowed by modular ordering. Begin with >=16 quiet
observations of every pad, or supply explicit initial baselines separately.
"""
from pathlib import Path
import argparse,csv,json
ROOT=Path(__file__).resolve().parents[1]

def load_trace(path):
    rows=[];last=None;elapsed=0
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'clock','channel','adc'}<=set(reader.fieldnames or []):
            raise ValueError('CSV requires clock,channel,adc')
        for line,r in enumerate(reader,2):
            try:t,ch,v=int(r['clock']),int(r['channel']),int(r['adc']);trigger=int(r.get('trigger','0') or 0)
            except (ValueError,TypeError) as e:raise ValueError(f'row {line}: integer fields required') from e
            if not(0<=t<2**32 and 0<=ch<=7 and 0<=v<=4095 and trigger in (0,1)):
                raise ValueError(f'row {line}: field outside ADC/clock/channel bounds')
            if last is not None:
                dt=(t-last)&0xffffffff
                if not 0<dt<2**31:raise ValueError(f'row {line}: timestamps not in forward order')
                elapsed+=dt
            last=t;rows.append({'clock':t,'elapsed_clock':elapsed,'channel':ch,'adc':v,'trigger':trigger})
    if not rows:raise ValueError('empty trace')
    return rows

def curve(profile,code,ch):
    s=next(s for s in profile['curve_segments'] if code<s['upper_exclusive'])
    v=s['base']+((max(0,code-s['origin'])*s['slope_q10'])>>10)
    return min(255,(v*profile['channel_gain_q8'][ch])>>8)

def replay(rows,profile,early,initial_baselines=None,on=280,off=100,peak_samples=4,rearm_samples=32):
    cal_samples=profile['automatic_zero_samples_per_channel']
    state=[dict(base=0,cal=0,armed=False,left=0,rearm=0,peak=0,previous=0,settled=0,fired=False) for _ in range(7)]
    if initial_baselines is not None:
        if len(initial_baselines)!=7 or any(type(v)!=int or not 0<=v<=4095 for v in initial_baselines):
            raise ValueError('initial baseline JSON must be seven integer ADC codes')
        for s,b in zip(state,initial_baselines):s.update(base=b,cal=cal_samples,armed=True)
    events=[]
    for r in rows:
        ch=r['channel']
        if ch==7:continue # The actual product uses AI7 for the potentiometer.
        s=state[ch];exc=max(0,r['adc']-s['base']);previous=s['previous'];s['previous']=exc
        level=curve(profile,exc,ch) if s['cal']==cal_samples and not s['armed'] and exc>=on else None
        strike=None;tag=False
        if s['cal']<cal_samples:
            s.update(base=r['adc'],previous=0,cal=s['cal']+1,armed=True)
        elif s['left']:
            s['peak']=max(s['peak'],exc)
            s['settled']=min(3,s['settled']+1) if exc>=on and exc<=previous else 0
            if s['left']==1:
                s.update(left=0,rearm=rearm_samples)
                if s['fired']:level=curve(profile,s['peak'],ch)
                else:strike=curve(profile,s['peak'],ch)
            else:
                s['left']-=1
                if (early and peak_samples>profile['early_policy']['settled_follow_samples'] and
                    not s['fired'] and s['settled']>=profile['early_policy']['settled_follow_samples'] and
                    s['peak']>=on+profile['early_policy']['peak_margin_codes']):
                    strike=curve(profile,s['peak'],ch);tag=True;s['fired']=True
        else:
            old_rearm=s['rearm']
            if old_rearm:s['rearm']-=1
            if s['armed'] and exc>=on:s.update(armed=False,peak=exc,fired=False,settled=0,left=peak_samples)
            elif not s['armed'] and old_rearm==0 and exc<=off:
                s['armed']=True
                if r['adc']<s['base']:s['base']-=((s['base']-r['adc'])//32)
            elif s['armed'] and exc<=off and r['adc']<s['base']:
                s['base']-=((s['base']-r['adc'])//32)
        if strike is not None or level is not None:
            events.append({**r,'strike':strike,'strike_early':tag,'level':level})
    if any(s['cal']<cal_samples for s in state):
        raise ValueError('trace lacks startup quiet samples for all seven pads; provide longer trace or explicit baseline JSON')
    return events

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv');p.add_argument('--profile',default=str(ROOT/'config/pressure_profile_v1.json'))
    p.add_argument('--baseline-json',help='Optional saved seven-code initial baseline array. Use only for the matching capture.')
    p.add_argument('--output',required=True);p.add_argument('--synthetic',action='store_true')
    a=p.parse_args();rows=load_trace(a.csv);profile=json.loads(Path(a.profile).read_text(encoding='utf-8'))
    baseline=json.loads(Path(a.baseline_json).read_text()) if a.baseline_json else None
    legacy=replay(rows,profile,False,baseline);early=replay(rows,profile,True,baseline)
    old_notes=[r for r in legacy if r['strike'] is not None];new_notes=[r for r in early if r['strike'] is not None]
    # Match by pad and ordinal. Early events can reorder interleaved pad events.
    comparisons=[];matched=True
    for ch in range(7):
        old=[r for r in old_notes if r['channel']==ch];new=[r for r in new_notes if r['channel']==ch]
        if len(old)!=len(new):matched=False;continue
        for o,n in zip(old,new):comparisons.append({'channel':ch,'saved_clocks':o['elapsed_clock']-n['elapsed_clock'],
            'old_velocity':o['strike'],'provisional_velocity':n['strike'],'early':n['strike_early']})
    report={'profile':profile['profile_name'],'input_csv':str(Path(a.csv).resolve()),'samples':len(rows),
        'evidence_kind':'synthetic' if a.synthetic else 'supplied trace; provenance not independently verified',
        'legacy_note_count':len(old_notes),'candidate_note_count':len(new_notes),'same_note_counts_by_pad':matched,
        'early_count':sum(x['strike_early'] for x in new_notes),'comparisons':comparisons,
        'candidate_events':early,'trained_model':False,'physical_latency_claim':False}
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('comparisons','candidate_events')},ensure_ascii=False))
    if not matched:raise SystemExit('NOTE counts differ; inspect trace and replay events before accepting this profile')

if __name__=='__main__':main()
