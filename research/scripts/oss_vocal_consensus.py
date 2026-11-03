"""Experimental sequence consensus of three trained transcription baselines.

Only PCM-derived note events are accepted. References, keys and lyrics have no
entry point. Constant weights are shared by every recording. A small Viterbi
switch cost suppresses unsupported boundary jitter; learned repeated attacks
remain explicit events instead of being silently merged into held notes.
"""
import numpy as np

def dense(ns,T,polyphonic=False):
    labels=np.zeros(T,dtype=np.int16);confidence=np.zeros(T)
    for q in ns:
        a=max(0,int(np.ceil(q['start_ms']/10)));z=min(T,int(np.ceil((q['start_ms']+q['duration_ms'])/10)))
        if polyphonic:
            # Basic Pitch is polyphonic: a documented maximum-activation
            # monophonic reduction, not a claim that raw MIDI is monophonic.
            use=confidence[a:z]<q['confidence'];labels[a:z][use]=q['midi'];confidence[a:z][use]=q['confidence']
        else:labels[a:z]=q['midi']
    return labels

def recognize_consensus(game,rosvot,basic,length_ms):
    T=(length_ms+9)//10;K=129
    # Index 0 is rest; 1..128 map to MIDI 0..127. Singing notes normally >0.
    tracks=[dense(game,T),dense(rosvot,T),dense(basic,T,True)]
    states=np.arange(K)-1
    emission=np.zeros((T,K),np.float32)
    for labels,weight in zip(tracks,[1.,.7,.7]):
        v=labels>0
        costs=np.minimum(abs(states[None,:]-labels[:,None]),2).astype(np.float32)
        costs[v,0]=1.2;costs[~v,:]=.9;costs[~v,0]=0
        emission+=costs*weight
    # Boundary agreement changes timing prior, never pitch identities.
    support=np.zeros(T,dtype=np.int8)
    for seq in [game,rosvot,basic]:
        mask=np.zeros(T,dtype=bool)
        for n in seq:
            k=round(n['start_ms']/10);mask[max(0,k-4):min(T,k+5)]=True
        support+=mask
    switch=np.where(support>=2,1.2,5.).astype(np.float32)
    score=emission[0].copy();back=np.empty((T,K),np.uint8);back[0]=np.arange(K)
    ids=np.arange(K,dtype=np.uint8)
    for t in range(1,T):
        best=int(np.argmin(score));candidate=score[best]+switch[t]
        change=candidate<score
        back[t]=np.where(change,best,ids)
        score=np.where(change,candidate,score)+emission[t]
    path=np.empty(T,np.int16);path[-1]=int(np.argmin(score))
    for t in range(T-1,0,-1):path[t-1]=back[t,path[t]]
    labels=path-1;labels[path==0]=0
    boundaries=set(np.flatnonzero(labels[1:]!=labels[:-1])+1)
    # Same-key rearticulations learned by GAME stay explicit; the sequence
    # decoder must not mistake them for a continuous hold.
    for a,z in zip(game,game[1:]):
        if a['midi']==z['midi'] and abs(a['start_ms']+a['duration_ms']-z['start_ms'])<=20:
            k=round(z['start_ms']/10)
            if 0<k<T and labels[k]==z['midi'] and labels[k-1]==z['midi']:boundaries.add(k)
    cuts=[0]+sorted(boundaries)+[T];out=[]
    for a,z in zip(cuts,cuts[1:]):
        if labels[a]>0:out.append({'start_ms':a*10,'duration_ms':min(length_ms,z*10)-a*10,
                                  'midi':int(labels[a]),'confidence':0.0})
    return out
