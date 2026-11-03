"""One coherent melody from a polyphonic transcription of a monophonic input.

The model can emit a subharmonic alongside the sung note. Unambiguous events
anchor the register; simultaneous alternatives compete as discrete pitches.
This stage never averages octaves or creates new onsets from F0 fluctuations.
"""
import numpy as np


def weighted_quantile(x,w,q):
    order=np.argsort(x);x=np.asarray(x)[order];w=np.asarray(w)[order]
    return float(np.interp(q*np.sum(w),np.cumsum(w)-w/2,x))


def select_melody(raw_notes,context_estimates=None):
    if not raw_notes:return [],{'groups':[],'reference_or_lyrics_used':False}
    groups=[]
    for n in sorted(raw_notes,key=lambda q:(q['start_ms'],q['midi'])):
        if n['duration_ms']<=0:continue
        if groups and n['start_ms']-groups[-1][0]['start_ms']<=30:groups[-1].append(n)
        else:groups.append([n])
    # One event per onset group. Same-pitch repeated words remain separate
    # groups, even with zero silence between their onsets.
    anchors=[g[0] for g in groups if len({n['midi'] for n in g})==1 and g[0]['duration_ms']>=120]
    if anchors:
        x=[n['midi'] for n in anchors];w=[min(1000,n['duration_ms']) for n in anchors]
        center=weighted_quantile(x,w,.5);spread=max(5.,(weighted_quantile(x,w,.8)-weighted_quantile(x,w,.2))*.7)
    else:
        center=float(np.median([n['midi'] for g in groups for n in g]));spread=10.
    emissions=[]
    for i,g in enumerate(groups):
        longest=max(q['duration_ms'] for q in g)
        cost=np.array([.4*((q['midi']-center)/spread)**2+.25*(1-q['duration_ms']/longest) for q in g])
        if context_estimates is not None:
            estimates=np.asarray(context_estimates[i],float);estimates=estimates[np.isfinite(estimates)&(estimates>24)]
            if len(estimates):
                # Alternative registers remain discrete modes. An estimate at
                # C4 and one at C5 cannot become a nonexistent F#4 vote.
                likelihood=np.exp(-.5*((np.array([q['midi'] for q in g])[:,None]-estimates)/.9)**2).mean(axis=1)
                cost+=.9*-np.log(likelihood+.025)
        emissions.append(cost)
    score=emissions[0].copy();back=[None]
    for i,g in enumerate(groups[1:],1):
        previous=groups[i-1]
        distances=abs(np.array([q['midi'] for q in previous])[:,None]-np.array([q['midi'] for q in g])[None,:])
        gap=max(0,min(q['start_ms'] for q in g)-max(q['start_ms']+q['duration_ms'] for q in previous))
        transition=.055*distances+.018*np.maximum(distances-7,0)**2
        if gap>=350:transition*=.2
        matrix=score[:,None]+transition
        b=matrix.argmin(axis=0);back.append(b);score=matrix[b,np.arange(len(g))]+emissions[i]
    path=np.zeros(len(groups),int);path[-1]=score.argmin()
    for i in range(len(groups)-1,0,-1):path[i-1]=back[i][path[i]]
    out=[];audit=[]
    for i,(g,j) in enumerate(zip(groups,path)):
        n=dict(g[j]);start=n['start_ms'];end=start+n['duration_ms']
        if i+1<len(groups):end=min(end,min(q['start_ms'] for q in groups[i+1]))
        if end>start:out.append({k:n[k] for k in ['start_ms','midi','confidence']}|{'duration_ms':end-start})
        audit.append({'start_ms':start,'candidate_pitches':[q['midi'] for q in g],'selected_midi':n['midi'],
                      'raw_offset_ms':n['start_ms']+n['duration_ms'],'selected_offset_ms':end})
    return out,{'policy':'simultaneous-candidates-register-path-v1','groups':audit,
                'unambiguous_anchor_notes':len(anchors),'register_center':center,'register_spread':spread,
                'raw_notes':len(raw_notes),'melody_notes':len(out),'new_onsets_from_F0':False,'reference_or_lyrics_used':False}
