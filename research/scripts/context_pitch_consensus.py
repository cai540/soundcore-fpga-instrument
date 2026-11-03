"""Conservative intended-pitch re-estimation across fixed-boundary contexts.

Only same-audio trained-model views and continuous pitch observations enter.
The input note schedule is immutable and no editorial score is read.
"""
import numpy as np
from grounded_pitch_decoder import hz_to_midi
from vocal_pitch_center import estimate_center

def refine_context(notes,context_views,evidence,pesto,tonality,semantic_notes=None):
    rp=hz_to_midi(evidence['rmvpe']);pp=pesto['midi'];pc=pesto['confidence']
    allowed=set(tonality['pitch_classes']) if tonality['enabled'] else None
    result=[];audit=[]
    for i,n in enumerate(notes):
        old=n['midi'];new=old;reasons=[]
        raw=np.array([v[i] for v in context_views]);classes=np.mod(raw,12)
        # Voting over classes does not average separate registers.
        votes=np.array([np.sum(abs((classes-k+6)%12-6)<.48) for k in range(12)])
        cls=int(votes.argmax());proposal=old+int((cls-old+6)%12-6)
        a=n['start_ms']//10;z=(n['start_ms']+n['duration_ms'])//10
        trim=min(3,max(0,(z-a)//10));a+=trim;z-=min(2,trim)
        centers=[];fits=[]
        for signal,valid in [(rp,rp>24),(pp,pc>.5)]:
            x=np.asarray(signal[a:z],float);ok=valid[a:z]&(x>24)
            x=x[ok];t=np.arange(a,z)[ok]*.01
            if len(x)<5:continue
            aliases=x[:,None]+np.array([-24,-12,0,12,24])[None,:]
            x=aliases[np.arange(len(x)),np.argmin(abs(aliases-old),axis=1)]
            x_ok=abs(x-old)<5;x=x[x_ok];t=t[x_ok]
            fit=estimate_center(t,x);fits.append(fit)
            if fit.get('vibrato'):centers.append(fit['center'])
            elif len(x):centers.append(float(np.median(x)))
        if votes[cls]>=2 and proposal!=old and abs(proposal-old)<=3 and len(centers)==2:
            center=float(np.mean(centers))
            if (max(centers)-min(centers)<.65 and abs(center-proposal)<.65
                and abs(center-old)-abs(center-proposal)>.2 and (allowed is None or proposal%12 in allowed)):
                new=int(proposal);reasons.append('context_class_with_continuous_center')
        # A word-aware model can disambiguate a low-period alias. Require
        # nearby melodic anchors and at least one independent context view.
        if semantic_notes and 0<i<len(notes)-1:
            overlaps=[]
            for s in semantic_notes:
                overlap=max(0,min(n['start_ms']+n['duration_ms'],s['start_ms']+s['duration_ms'])-max(n['start_ms'],s['start_ms']))
                if overlap:overlaps.append((overlap,s))
            if overlaps:
                overlap,s=max(overlaps,key=lambda q:q[0])
                choices=new+np.array([-24,-12,0,12,24]);target=int(choices[np.argmin(abs(choices-s['midi']))])
                near=max(abs(target-notes[i-1]['midi']),abs(target-notes[i+1]['midi']))
                context_support=bool(np.any(abs(raw-target)<1.))
                if overlap>=n['duration_ms']*.55 and abs(target-new)==12 and abs(target-s['midi'])<=2 and near<=6 and context_support:
                    new=target;reasons.append('word_model_register_and_context')
        result.append({**n,'midi':new})
        audit.append({'start_ms':n['start_ms'],'old_midi':old,'new_midi':new,'context_midi':raw.tolist(),
                      'class_votes':votes.tolist(),'centers':centers,'reasons':reasons or ['retain']})
    return result,{'notes':audit,'changes':sum(a['midi']!=b['midi'] for a,b in zip(notes,result)),
                   'schedule_unchanged':True,'reference_used':False}
