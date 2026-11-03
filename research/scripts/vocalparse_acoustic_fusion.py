"""Fuse audio-inferred word/note structure with measured continuous pitch.

The language model supplies a weak intended-note/register prior. Stable
acoustic evidence can correct it. Genuine sustained components are retained;
same-vowel jitter is pooled, never averaged into an in-between octave.
"""
import numpy as np
from vocalparse_time_alignment import align_units,BEATS
from grounded_pitch_decoder import hz_to_midi
from vocal_pitch_center import estimate_center

def component_units(parsed):
    units=[];group=-1;barrier=True
    for word,pitch,note in zip(parsed['words'],parsed['pitches'],parsed['notes']):
        if word in ['AP','SP'] or pitch==0:barrier=True;continue
        continuation=word=='·' and not barrier and bool(units)
        if not continuation:group+=1
        units.append({'word':word,'midi':int(pitch),'seed_midi':int(pitch),'group':group,
                      'beats':BEATS.get(note,1.),'components':[(int(pitch),BEATS.get(note,1.))],
                      'onset_weight':0. if continuation else 1.})
        barrier=False
    return units

def observed(n,seed,evidence,pesto):
    a=(n['start_ms']+9)//10;z=(n['start_ms']+n['duration_ms']+9)//10
    trim=min(3,max(0,(z-a)//10));a+=trim;z-=min(2,trim)
    result=[]
    for raw,confidence in [(hz_to_midi(evidence['rmvpe']),None),(pesto['midi'],pesto['confidence'])]:
        x=np.asarray(raw[a:z],float);w=np.ones(len(x)) if confidence is None else np.asarray(confidence[a:z],float)
        valid=(x>24)&(w>.5);x=x[valid];t=np.arange(a,z)[valid]*.01
        if not len(x):result.append((t,x));continue
        aliases=x[:,None]+np.array([-24,-12,0,12,24])[None,:]
        v=aliases[np.arange(len(x)),np.argmin(abs(aliases-seed),axis=1)]
        good=abs(v-seed)<=7;result.append((t[good],v[good]))
    return result

def acoustic_pitch(n,seed,evidence,pesto,prior,tonality=None):
    tracks=observed(n,seed,evidence,pesto);options=np.arange(max(24,seed-7),min(108,seed+7)+1)
    mass=np.zeros(len(options));used=0;fits=[];spread=[]
    for t,x in tracks:
        if len(x)<5:continue
        h=np.exp(-.5*((options[:,None]-x)/.55)**2).mean(axis=1)
        fit=estimate_center(t,x);fits.append(fit);spread.append(float(np.quantile(x,.8)-np.quantile(x,.2)))
        if fit.get('vibrato'):
            center_h=np.exp(-.5*((options-fit['center'])/.7)**2)
            h=.45*h+.55*center_h
        mass+=h;used+=1
    if not used:return int(seed),{'periodic':False,'support':0.,'reason':'no_voiced_pitch_evidence'}
    mass/=used
    periodic=(len(fits)==2 and all(f.get('vibrato') for f in fits)
              and abs(fits[0]['center']-fits[1]['center'])<.65)
    allowed=set(tonality['pitch_classes']) if tonality and tonality['enabled'] else None
    semantic=.9 if periodic and (allowed is None or seed%12 in allowed) else .25
    costs=-np.log(mass+.02)+semantic*np.minimum(abs(options-seed),4)
    costs+=-.35*np.log(np.maximum(prior[options%12],.04))
    # Only broad/ambiguous observations use this recording-derived collection.
    # Two concordant stable tracks protect even a rare, clear chromatic note.
    clear_stable=len(spread)==2 and max(spread)<.42
    if allowed is not None and not clear_stable:
        costs+=np.array([0. if p%12 in allowed else 2. for p in options])
    j=int(np.argmin(costs));pitch=int(options[j])
    return pitch,{'periodic':bool(periodic),'support':float(mass[j]),'seed':int(seed),'chosen':pitch,
                  'fits':fits,'spread':spread,'reason':'continuous_acoustic_and_intended_note'}

def word_pool(notes,units,evidence,pesto,prior,tonality=None):
    out=[];groups=[]
    for i,u in enumerate(units):
        if not groups or groups[-1][0]!=u['group']:groups.append((u['group'],[i]))
        else:groups[-1][1].append(i)
    audit=[]
    for group,indexes in groups:
        ns=[notes[i] for i in indexes];us=[units[i] for i in indexes]
        if len(ns)==1:out.extend(ns);continue
        if any(b['start_ms']-a['start_ms']-a['duration_ms']>=80 for a,b in zip(ns,ns[1:])):
            out.extend(ns);continue
        span={**ns[0],'duration_ms':ns[-1]['start_ms']+ns[-1]['duration_ms']-ns[0]['start_ms']}
        by_pitch={}
        for n in ns:by_pitch[n['midi']]=by_pitch.get(n['midi'],0)+n['duration_ms']
        seed=max(by_pitch,key=by_pitch.get);main,full=acoustic_pitch(span,seed,evidence,pesto,prior,tonality)
        reliable=[]
        for i,n in enumerate(ns):
            p,a=acoustic_pitch(n,n['midi'],evidence,pesto,prior,tonality)
            if n['duration_ms']>=180 and a['support']>.24:reliable.append(i)
        distinct=len(set(ns[i]['midi'] for i in reliable))>=2
        if distinct and not full['periodic']:
            # Preserve clear, sustained melodic components; at most two for
            # one inferred word. Choose by duration, then keep temporal order.
            keep=sorted(sorted(reliable,key=lambda i:ns[i]['duration_ms'],reverse=True)[:2])
            split=ns[keep[1]]['start_ms']
            out.append({**ns[0],'midi':ns[keep[0]]['midi'],'duration_ms':split-ns[0]['start_ms']})
            out.append({**ns[keep[1]],'duration_ms':span['start_ms']+span['duration_ms']-split})
            action='retained_two_sustained_components'
        else:
            out.append({**span,'midi':main});action='pooled_one_vowel_main_note'
        audit.append({'group':group,'word':us[0]['word'],'action':action,'original_components':ns,'main_evidence':full})
    return out,audit

def decode_fused(pcm,parsed,evidence,pesto,tonality=None):
    units=component_units(parsed)
    if not units:return [],{'accepted':False,'reason':'no_units'}
    histogram=np.bincount(np.array([u['seed_midi'] for u in units])%12,
        weights=np.array([u['beats'] for u in units]),minlength=12)+1.
    prior=histogram/histogram.max();pitch_audit=[]
    for iteration in range(2):
        notes,alignment=align_units(pcm,parsed,evidence,pesto,units_override=units)
        if len(notes)!=len(units):return notes,alignment
        for n,u in zip(notes,units):
            pitch,a=acoustic_pitch(n,u['seed_midi'],evidence,pesto,prior,tonality)
            pitch_audit.append({'iteration':iteration,'start_ms':n['start_ms'],'word':u['word'],**a})
            u['midi']=pitch
    notes,alignment=align_units(pcm,parsed,evidence,pesto,units_override=units)
    if len(notes)!=len(units):return notes,alignment
    out,pool_audit=word_pool(notes,units,evidence,pesto,prior,tonality)
    return out,{**alignment,'fusion_policy':'word_structure_continuous_pitch_v1','pitch_evidence':pitch_audit,
                'pooling':pool_audit,'component_notes_before_pooling':len(notes),'notes_after_pooling':len(out),
                'recording_tonality':tonality}
