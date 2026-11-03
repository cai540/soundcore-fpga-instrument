"""A melody path through complete note INTERVALS, rather than all onsets.

A late subharmonic note is an optional competing hypothesis, not an order
to truncate the currently sounding vowel. Starts always come from trained
transcription models; frame F0 cannot create an attack. Source gaps remain.
"""
import numpy as np
from note_probability_fusion import basic_times

def build_hypotheses(primary,alternate,phonetic=None):
    # The primary model supplies the attack seeds. Offsets and register may
    # compete, but an alternate model alone cannot silently increase the
    # number of attacks. This prevents staggered duplicate emissions from
    # both models being rendered as a rapid arpeggio.
    normalized=[];anchor=None
    for n in sorted(primary,key=lambda q:(q['start_ms'],q['midi'])):
        n=dict(n);end=n['start_ms']+n['duration_ms']
        if anchor is None or n['start_ms']-anchor>30:anchor=n['start_ms']
        n['start_ms']=anchor;n['duration_ms']=end-anchor;normalized.append(n)
    primary=normalized
    out=[]
    # Match identical notes by both boundaries, never just a pitch label.
    for origin,notes in [('primary',primary),('alternate',alternate)]:
        for n in notes:
            if n['duration_ms']<60 or not 24<=n['midi']<=100:continue
            n=dict(n)
            a=n['start_ms'];z=a+n['duration_ms'];best=None
            if origin=='alternate':
                # Two models may place the SAME onset a few frames apart.
                # Keep those as pitch/offset alternatives at one primary
                # onset, rather than inventing a rapid extra reattack.
                nearby=[h for h in out if 'primary' in h['origins'] and abs(h['start_ms']-a)<=70]
                if not nearby:continue
                if nearby:
                    anchor=min(nearby,key=lambda h:abs(h['start_ms']-a))['start_ms']
                    a=anchor;n['start_ms']=a;n['duration_ms']=z-a
                for h in out:
                    if h['midi']!=n['midi'] or 'alternate' in h['origins']:continue
                    offset=h['start_ms']+h['duration_ms']
                    if abs(h['start_ms']-a)<=70 and abs(offset-z)<=max(90,.15*n['duration_ms']):
                        distance=abs(h['start_ms']-a)+abs(offset-z)
                        if best is None or distance<best[0]:best=(distance,h)
            if best is not None:
                best[1]['origins'].append(origin)
            else:out.append({**n,'origins':[origin]})
    # A harmonic duplicate can also be late within the primary model itself.
    # Require matching offsets and extensive overlap, and preserve a strong
    # independently measured phonetic reattack.
    ordered=sorted(out,key=lambda n:(n['start_ms'],n['midi'],n['duration_ms']))
    for i,n in enumerate(ordered):
        a=n['start_ms'];z=a+n['duration_ms'];k=a//10
        strong=phonetic is not None and float(np.max(phonetic[max(0,k-4):min(len(phonetic),k+5)]))>.65
        if strong:continue
        for h in ordered[:i]:
            b=h['start_ms'];e=b+h['duration_ms']
            if not 0<a-b<=100 or abs(n['midi']-h['midi']) not in (12,24):continue
            overlap=min(z,e)-max(a,b)
            if abs(z-e)<=120 and overlap>=.7*min(z-a,e-b):
                n['start_ms']=b;n['duration_ms']=z-b;break
    return sorted(ordered,key=lambda n:(n['start_ms'],n['midi'],n['duration_ms']))

def decode_lattice(primary,alternate,evidence,pesto,basic,acoustic):
    hypotheses=build_hypotheses(primary,alternate,evidence.get('word'))
    if not hypotheses:return [],{'policy':'complete-interval-melody-lattice-v1','hypotheses':[]}
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    word=evidence['word'];rms=acoustic['rms'];bp_values=np.asarray(basic['note']);bt=basic_times(len(bp_values))
    pesto_values=np.asarray(pesto['midi']);pesto_confidence=np.asarray(pesto['confidence'])
    energy_floor=max(1e-5,float(np.quantile(rms,.9))*.035)
    rates=[];birth=[];attacks=[];details=[];retained=[];rejected=[]
    primary_starts=np.array([n['start_ms'] for n in primary])
    for h in hypotheses:
        a=h['start_ms'];z=a+h['duration_ms'];s=(a+29)//10;e=min(len(rm),(z-20+9)//10)
        k=min(len(word)-1,a//10);attack=float(np.max(word[max(0,k-5):min(len(word),k+6)]))
        v=rms[s:e];voiced=float(np.mean(v>energy_floor)) if len(v) else 0.
        r=rm[s:e];r=r[np.isfinite(r)]
        p=pesto_values[s:e][pesto_confidence[s:e]>.6]
        support=[];register=[]
        for values in [r,p]:
            if len(values)<5:continue
            d=(values-h['midi']+6)%12-6
            support.append(float(np.mean(np.exp(-.5*(d/.9)**2))))
            register.append(float(np.mean(np.exp(-.5*((values-h['midi'])/1.5)**2))))
        x,y=np.searchsorted(bt,[(a+30)/1000,(z-20)/1000])
        b=bp_values[x:y].mean(axis=0) if y>x else np.zeros(88)
        bp=float(b[h['midi']-21]);class_support=float(np.mean(support)) if support else 0.
        exact_support=float(np.mean(register)) if register else 0.
        near_primary=bool(len(primary_starts) and np.min(abs(primary_starts-a))<=70)
        # A larger model must not inject all of its unsupported extra attacks.
        # It can propose a sustained interval at an existing onset; a truly
        # new onset needs both a phonetic attack and strong source evidence.
        if (h['origins']==['alternate'] and not near_primary
            and not (attack>.65 and class_support>.65 and bp>.2 and voiced>.7)):
            rejected.append({'start_ms':a,'midi':h['midi'],'reason':'unconfirmed_alternate_only_attack'})
            continue
        retained.append(h)
        both=len(h['origins'])==2
        # Symbolic agreement estimates the intended note; F0 register votes
        # are weak because all period estimators can share a subharmonic.
        rate=(1.0 if 'primary' in h['origins'] else .82)+(.85 if both else 0.)
        rate+=.45*class_support+.18*exact_support+.15*min(bp/.3,1)+.25*voiced
        if voiced<.3 and class_support<.2 and bp<.08:rate=-.5
        attack_gain=.27*attack-.11
        rates.append(rate);birth.append(attack_gain);attacks.append(attack)
        details.append({'start_ms':a,'duration_ms':h['duration_ms'],'midi':h['midi'],'origins':h['origins'],
                        'rate':rate,'birth_score':attack_gain,'phonetic_attack':attack,'voiced_fraction':voiced})
    hypotheses=retained
    if not hypotheses:return [],{'policy':'complete-interval-melody-lattice-v2','hypotheses':[],'rejected':rejected}
    rates=np.asarray(rates);birth=np.asarray(birth);starts=np.array([n['start_ms'] for n in hypotheses])
    ends=np.array([n['start_ms']+n['duration_ms'] for n in hypotheses]);pitches=np.array([n['midi'] for n in hypotheses])
    score=np.full(len(hypotheses),-1e12);back=np.full(len(hypotheses),-1,int)
    for i,h in enumerate(hypotheses):
        score[i]=birth[i]
        # A real later onset is allowed to truncate an overlong previous
        # prediction. Comparing the two RAW offsets here incorrectly removed
        # a short middle syllable entirely when the previous note overhung it.
        eligible=np.flatnonzero(starts[:i]<starts[i]-59)
        if not len(eligible):continue
        used=np.minimum(ends[eligible],starts[i])-starts[eligible]
        gap=np.maximum(starts[i]-ends[eligible],0);overlap=np.maximum(ends[eligible]-starts[i],0)
        distance=abs(pitches[eligible]-pitches[i])
        transition=(.022*distance+.007*np.maximum(distance-7,0)**2)*np.where(gap>350,.2,1.)
        # A weak attack is not sufficient to cut into a still-active note.
        cut=(np.minimum(overlap,500)/1000)*(.45 if attacks[i]<.6 else .10)
        values=score[eligible]+rates[eligible]*used/1000-transition-cut+birth[i]
        j=int(np.argmax(values))
        if values[j]>score[i]:score[i]=values[j];back[i]=eligible[j]
    final=score+rates*(ends-starts)/1000
    path=[];i=int(final.argmax())
    while i>=0:path.append(i);i=int(back[i])
    path=path[::-1];notes=[]
    for k,i in enumerate(path):
        h=hypotheses[i];end=int(ends[i])
        if k+1<len(path):end=min(end,int(starts[path[k+1]]))
        if rates[i]<=0 or end<=h['start_ms']:continue
        notes.append({'start_ms':h['start_ms'],'duration_ms':end-h['start_ms'],'midi':h['midi'],'confidence':0.})
    selected=set(path)
    for i,h in enumerate(details):h['selected']=i in selected
    return notes,{'policy':'complete-interval-melody-lattice-v4','hypotheses':details,'rejected':rejected,
                   'selected_path':path,'onsets_forced_by_F0':False,'reference_lyrics_or_identity_used':False,
                   'candidate_notes':len(hypotheses),'selected_notes':len(notes)}
