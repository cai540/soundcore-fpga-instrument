"""Discrete consensus of two complete-event models and acoustic evidence.

The bigger model is a fallible alternate, not a replacement. Its notes must
time-align acoustically with the primary event. No expected melody, lyrics,
song key or fixed note count is accepted.
"""
import numpy as np
from recording_tonality import infer_collection
from monophonic_event_path import select_melody
from note_probability_fusion import basic_times

def aligned_alternates(note,alternate):
    a=note['start_ms'];z=a+note['duration_ms'];out=[]
    for q in alternate:
        b=q['start_ms'];e=b+q['duration_ms'];overlap=max(0,min(z,e)-max(a,b))
        if abs(b-a)<=min(140,max(60,note['duration_ms']*.3)) and overlap>=min(z-a,e-b)*.55:
            out.append(q)
    return out

def consensus_events(raw,alternate,views,evidence,pesto,crepe,basic,note_schedule=None,confirmation=None):
    if note_schedule is None:
        primary,group_audit=select_melody(raw);groups=group_audit['groups']
    else:
        primary=note_schedule
        groups=[{'candidate_pitches':sorted({q['midi'] for q in aligned_alternates(n,raw)} or {n['midi']})} for n in primary]
    tonal=infer_collection(primary)
    allowed=set(tonal['pitch_classes']) if tonal['enabled'] else None
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    cr=np.where(crepe['f0']>0,69+12*np.log2(np.maximum(crepe['f0'],1)/440),np.nan)
    bp_values=np.asarray(basic['note']);times=basic_times(len(bp_values));candidates=[];costs=[];audit=[]
    pesto_values=np.asarray(pesto['midi']);pesto_confidence=np.asarray(pesto['confidence']);crepe_periodicity=np.asarray(crepe['periodicity'])
    for i,(n,g) in enumerate(zip(primary,groups)):
        med=np.array(sorted(set(g['candidate_pitches'])),int)
        alt=aligned_alternates(n,alternate);large=np.array(sorted({q['midi'] for q in alt}),int)
        check=aligned_alternates(n,confirmation or []);small=np.array(sorted({q['midi'] for q in check}),int)
        # New classes require a time-aligned alternate event within a whole
        # tone of an existing class. Harmonic/octave hypotheses stay discrete.
        additions=[k for k in large if np.min(abs((med-k+6)%12-6))<=2]
        additions += [k for k in small if np.min(abs((med-k+6)%12-6))<=1]
        options=np.array(sorted(set(med.tolist()+additions)),int)
        s=(n['start_ms']+min(50,n['duration_ms']//8)+9)//10
        e=min(len(rm),(n['start_ms']+n['duration_ms']-min(30,n['duration_ms']//8)+9)//10)
        context=np.asarray(views)[:,i];context=context[np.isfinite(context)&(context>24)]
        def likelihood(values,width):
            if not len(values):return np.zeros(len(options))
            # Each model family contributes one total unit, irrespective of
            # how many harmonically duplicated notes it emitted.
            return np.exp(-.5*((options[:,None]-values)/width)**2).mean(axis=1)
        medium=likelihood(med,.42);other=likelihood(large,.42);game=likelihood(context,.7)
        source=[]
        for v,valid in [(rm,rm>24),(pesto_values,pesto_confidence>.6),(cr,crepe_periodicity>.15)]:
            x=v[s:e][valid[s:e]];x=x[np.isfinite(x)]
            if len(x)>=6:source.append(likelihood(x,1.1))
        track=np.mean(source,axis=0) if source else np.zeros(len(options))
        x,y=np.searchsorted(times,[s/100,e/100]);bp=bp_values[x:y].mean(axis=0) if y>x else np.zeros(88)
        poly=np.array([bp[k-21] if 21<=k<=108 else 0. for k in options]);rel=float(np.clip(poly.max()/.3,0,1))
        poly/=max(poly.max(),.01)
        # Complete-note symbolic labels carry more intended-class evidence
        # than momentary sharp/flat vowel samples. Acoustic families remain
        # useful for choosing among raw octave aliases.
        value=1.8*medium+1.25*other+.65*game+.35*track+.2*rel*poly
        if len(small):value+=.65*likelihood(small,.42)
        cost=-np.log(value+.03)
        if allowed is not None:
            for j,k in enumerate(options):
                both=bool(np.any(med==k) and np.any(large==k))
                if k%12 not in allowed and not both:cost[j]+=.32
        candidates.append(options);costs.append(cost)
        audit.append({'start_ms':n['start_ms'],'medium_candidates':med.tolist(),'large_candidates':large.tolist(),'confirmation_candidates':small.tolist(),
                      'pitch_options':options.tolist(),'costs':cost.tolist(),'game_views':context.tolist()})
    if not candidates:return [],{'policy':'complete-event-consensus-v1','notes':[]}
    score=costs[0].copy();back=[None]
    for i in range(1,len(primary)):
        distance=abs(candidates[i-1][:,None]-candidates[i][None,:])
        gap=primary[i]['start_ms']-primary[i-1]['start_ms']-primary[i-1]['duration_ms']
        trans=(.025*distance+.008*np.maximum(distance-7,0)**2)*(.2 if gap>350 else 1.)
        matrix=score[:,None]+trans;b=matrix.argmin(axis=0);back.append(b)
        score=matrix[b,np.arange(len(candidates[i]))]+costs[i]
    path=np.zeros(len(primary),int);path[-1]=score.argmin()
    for i in range(len(path)-1,0,-1):path[i-1]=back[i][path[i]]
    out=[]
    for n,options,j,a in zip(primary,candidates,path,audit):
        a['midi']=int(options[j]);out.append({**n,'midi':a['midi']})
    return out,{'policy':'complete-event-consensus-v1','notes':audit,'recording_tonality':tonal,
                'reference_lyrics_or_song_identity_used':False,'onsets_from_full_event_model':True}

def merge_corroborated_sustain(notes,alternate,evidence,acoustic):
    """Two models must disagree on a reattack before it can be removed."""
    result=[];removed=[];word=evidence['word'];rms=acoustic['rms']
    for n in notes:
        merge=False
        if result and n['midi']==result[-1]['midi'] and n['start_ms']==result[-1]['start_ms']+result[-1]['duration_ms']:
            t=n['start_ms'];k=t//10
            holds=[q for q in alternate if q['midi']==n['midi'] and q['start_ms']<t-100
                   and q['start_ms']+q['duration_ms']>t+100]
            # The alternate may hold a subharmonic while reattacking the
            # actual voice an octave above it. That is still a reattack and
            # must protect the primary event from an incorrect merge.
            attacks=[q for q in alternate if abs(q['start_ms']-t)<90 and (q['midi']-n['midi'])%12==0]
            peak=float(np.max(word[max(0,k-5):min(len(word),k+6)]))
            if 15<=k<len(rms)-16:
                l=float(np.quantile(rms[k-15:k-3],.8));r=float(np.quantile(rms[k+3:k+15],.8))
                valley=float(np.min(rms[k-3:k+4]))/max(min(l,r),1e-8)
                merge=bool(holds and not attacks and peak<.3 and valley>.75)
            if merge:removed.append({'start_ms':t,'midi':n['midi'],'phonetic_peak':peak,'reason':'alternate_continuous_hold_and_no_phonetic_reattack'})
        if merge:result[-1]['duration_ms']+=n['duration_ms']
        else:result.append(dict(n))
    return result,{'removed_reattacks':removed,'rest_gaps_filled':0,'different_pitches_merged':0}
