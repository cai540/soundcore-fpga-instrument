"""Register path over discrete octave hypotheses from this recording only.

Pitch classes, note starts and lengths are immutable. Polyphonic note evidence
can expose a melody an octave above a dominant subharmonic. Acoustic agreement
is one fallible observation, never an absolute ground-truth veto.
"""
import numpy as np
from note_probability_fusion import basic_times


def decode_register(notes,basic,crepe,pesto,strength=1.):
    if not notes:return [],{}
    times=basic_times(len(basic['note']));bp=basic['note'].astype(float)
    cp=np.where(crepe['f0']>0,69+12*np.log2(np.maximum(crepe['f0'],1)/440),0.)
    shifts=np.array([-24,-12,0,12,24]);candidates=np.array([n['midi']+shifts for n in notes])
    costs=[];observations=[]
    for n,options in zip(notes,candidates):
        s=n['start_ms'];e=s+n['duration_ms'];edge=min(50,n['duration_ms']//8)
        a,z=np.searchsorted(times,[(s+edge)/1000,(e-edge)/1000])
        q=bp[a:z].mean(axis=0) if z>a else np.zeros(88)
        scores=np.array([q[p-21] if 21<=p<=108 else 0 for p in options])
        # Evaluate alias alternatives without averaging their MIDI values.
        activity=max(scores.max(),.01);relative=scores/max(activity,.12)
        cost=-np.log(relative+.035)*1.15+.15*(shifts!=0)
        cost+=np.maximum(0,.09-scores)*12
        a=(s+edge+9)//10;z=min(len(cp),(e-edge+9)//10)
        r=cp[a:z][crepe['periodicity'][a:z]>.15]
        p=pesto['midi'][a:z][pesto['confidence'][a:z]>.6]
        support=np.array([np.mean(np.exp(-.5*((v[:,None]-options)/1.)**2),axis=0)
                          for v in (r,p) if len(v)])
        if len(support):cost-=.35*support.mean(axis=0)
        cost[(options<24)|(options>100)]=1e6
        costs.append(cost);observations.append({'basic_probabilities':scores.tolist(),'tracker_support':support.tolist()})
    costs=np.array(costs);back=np.zeros(costs.shape,int);score=costs[0].copy()
    for i in range(1,len(notes)):
        distance=abs(candidates[i-1,:,None]-candidates[i,None,:])
        gap=notes[i]['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']
        trans=(.035*distance+.035*np.maximum(0,distance-5)**2)*strength
        trans*=.2 if gap>350 else 1.
        matrix=score[:,None]+trans
        back[i]=matrix.argmin(axis=0);score=matrix[back[i],np.arange(5)]+costs[i]
    path=np.zeros(len(notes),int);path[-1]=score.argmin()
    for i in range(len(notes)-1,0,-1):path[i-1]=back[i,path[i]]
    out=[];audit=[]
    for n,options,j,c,o in zip(notes,candidates,path,costs,observations):
        new=int(options[j]);out.append({**n,'midi':new})
        audit.append({'start_ms':n['start_ms'],'old_midi':n['midi'],'new_midi':new,
                      'candidate_pitches':options.tolist(),'emission_costs':c.tolist(),**o})
    return out,{'policy':'polyphonic-register-sequence-v1','notes':audit,
                'changes':sum(n['midi']!=q['midi'] for n,q in zip(notes,out)),
                'reference_used':False,'schedule_unchanged':True}
