"""Generic sequence-level octave inference on a frozen note schedule.

Pitch class is immutable. Competing registers are discrete states, never
averaged. Exact octaves remain possible; continuity only resolves ambiguity.
"""
import numpy as np
from grounded_pitch_decoder import hz_to_midi

OFFSETS=np.array([-24,-12,0,12,24])

def transition_cost(a,b,gap_ms):
    distance=np.abs(np.asarray(a)[:,None]-np.asarray(b)[None,:]).astype(float)
    octave=(np.remainder(distance,12)<.01)&(distance<=24)
    penalty=.04*distance+.22*np.maximum(distance-7,0)
    # Same pitch class and a clear exact octave is a common musical leap.
    # It must not be erased simply to make a smooth line.
    penalty=np.where(octave,.025*distance,penalty)
    return penalty*(.2 if gap_ms>=300 else 1.)

def decode_register(notes,evidence,pesto,melodia=None):
    if not notes:return [],{'notes':[],'policy':'octave-sequence-v1'}
    r=hz_to_midi(evidence['rmvpe']);p=np.asarray(pesto['midi'],float);conf=np.asarray(pesto['confidence'],float)
    f=hz_to_midi(evidence['fcpe']);fc=np.asarray(evidence['fcpe_confidence'],float)
    tracks=[(r,r>24,.7),(p,conf>.5,.7),(f,fc>.2,.3)]
    if melodia is not None:
        m=hz_to_midi(melodia['f0']);tracks.append((m,m>24,.8))
    candidates=[];costs=[];audits=[]
    for n in notes:
        options=n['midi']+OFFSETS;support=np.zeros(len(options));total=0.;details=[]
        for raw,valid,weight in tracks:
            a=max(0,(n['start_ms']+9)//10);z=min(len(raw),(n['start_ms']+n['duration_ms']+9)//10)
            trim=min(3,max(0,(z-a)//10));x=raw[a+trim:z-min(2,trim)];ok=valid[a+trim:z-min(2,trim)]
            x=x[ok]
            if len(x)<5:continue
            direct=np.mean(np.exp(-.5*((options[:,None]-x)/1.2)**2),axis=1)
            aliased=np.zeros(len(options))
            for shift in [-24,-12,12,24]:
                h=np.mean(np.exp(-.5*((options[:,None]-x-shift)/1.2)**2),axis=1)
                aliased=np.maximum(aliased,h*np.exp(-1.1*abs(shift)/12))
            # Several trackers can share a period error. Their votes remain a
            # mixture rather than a product that falsely multiplies certainty.
            likelihood=np.maximum(direct,aliased)
            support+=likelihood*weight;total+=weight
            details.append({'direct_support':direct.tolist(),'weight':weight})
        c=-np.log(support/max(total,1e-6)+.015)+np.abs(OFFSETS)/12*.12
        c[(options<24)|(options>108)]=1e6
        if not total:c=np.abs(OFFSETS).astype(float)
        candidates.append(options);costs.append(c);audits.append({'start_ms':n['start_ms'],'old_midi':n['midi'],
          'options':options.tolist(),'emission_cost':c.tolist(),'track_support':details})
    candidates=np.asarray(candidates);costs=np.asarray(costs);score=costs[0].copy();back=np.zeros(costs.shape,dtype=int)
    for i in range(1,len(notes)):
        gap=notes[i]['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']
        matrix=score[:,None]+transition_cost(candidates[i-1],candidates[i],gap)
        back[i]=matrix.argmin(axis=0);score=matrix[back[i],np.arange(len(OFFSETS))]+costs[i]
    path=np.zeros(len(notes),int);path[-1]=score.argmin()
    for i in range(len(notes)-1,0,-1):path[i-1]=back[i,path[i]]
    out=[]
    for n,options,j,audit in zip(notes,candidates,path,audits):
        pitch=int(options[j]);out.append({**n,'midi':pitch});audit['new_midi']=pitch
    return out,{'policy':'octave-sequence-v1','notes':audits,'changes':sum(a['midi']!=b['midi'] for a,b in zip(notes,out)),
                'pitch_class_unchanged':True,'schedule_unchanged':True,'reference_used':False}
