"""Full-note discrete pitch inference, with independent class/register evidence.

MuScriptor supplies events. GAME estimates fixed event regions. Continuous
trackers measure the vowel center; Basic Pitch supplies polyphonic evidence.
No score, transcript, title, target scale or reference pitch enters this API.
"""
import numpy as np
from note_probability_fusion import basic_times
from vocal_pitch_center import estimate_center

P=np.arange(24,101)

def distribution(values,weights=None):
    """Keep octave aliases as separate modes; demodulate only real vibrato."""
    v=np.asarray(values,float);w=np.ones(len(v)) if weights is None else np.asarray(weights,float)
    ok=np.isfinite(v)&(v>24)&(w>0);t=np.arange(len(v))*.01;v=v[ok];t=t[ok];w=w[ok]
    if len(v)<6:return np.ones(len(P)),{'usable':False}
    # Fold only to estimate a pitch CLASS, not to average register values.
    anchor=float(v[len(v)//2]);folded=anchor+(v-anchor+6)%12-6
    fit=estimate_center(t,folded,w)
    if fit.get('vibrato'):
        center=fit['center'];d=(P-center+6)%12-6
        classes=np.exp(-.5*(d/.42)**2)
    else:
        # A density, rather than the mean, preserves two actual plateaus.
        d=(P[:,None]-v+6)%12-6
        classes=np.average(np.exp(-.5*(d/.48)**2),weights=w,axis=1)
    register=np.average(np.exp(-.5*((P[:,None]-v)/1.6)**2),weights=w,axis=1)
    score=classes*(.32+.68*register/max(register.max(),.01))
    return score/max(score.max(),.01),{'usable':True,'vibrato':bool(fit.get('vibrato')),
              'vowel_center':fit['center'],'median_register':float(np.median(v))}

def decode_event_pitches(notes,views,evidence,pesto,crepe,basic):
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    cr=np.where(crepe['f0']>0,69+12*np.log2(np.maximum(crepe['f0'],1)/440),np.nan)
    bp_values=np.asarray(basic['note']);bt=basic_times(len(bp_values));costs=[];audits=[]
    for i,n in enumerate(notes):
        edge=min(60,n['duration_ms']//8);a=(n['start_ms']+edge+9)//10
        z=min(len(rm),(n['start_ms']+n['duration_ms']-min(edge,40)+9)//10)
        families=[];detail=[]
        for name,v,valid in [('rmvpe',rm,rm>24),('pesto',pesto['midi'],pesto['confidence']>.6),
                             ('crepe',cr,crepe['periodicity']>.15)]:
            values=v[a:z].copy();values[~valid[a:z]]=np.nan
            score,d=distribution(values);detail.append({'model':name,**d})
            if d['usable']:families.append(score)
        continuous=np.mean(families,axis=0) if families else np.ones(len(P))
        # Context views belong to ONE model family, not independent votes.
        vs=np.asarray(views)[:,i];vs=vs[np.isfinite(vs)&(vs>24)]
        context=np.exp(-.5*((P[:,None]-vs)/.65)**2).mean(axis=1) if len(vs) else np.ones(len(P))
        x,y=np.searchsorted(bt,[a/100,z/100]);bp=bp_values[x:y].mean(axis=0) if y>x else np.zeros(88)
        positive=np.maximum(bp-np.median(bp),0);poly=positive[P-21]
        reliability=float(np.clip(poly.max()/.3,0,1));poly/=max(float(poly.max()),.01)
        raw=np.exp(-.5*((P-n['midi'])/.62)**2)
        # Normalized additive likelihoods let one family disagree without
        # annihilating a real note. A model's label is not ground truth.
        likelihood=1.5*continuous+1.15*context+.9*reliability*poly+.55*raw
        cost=-np.log(likelihood+.035);costs.append(cost)
        audits.append({'start_ms':n['start_ms'],'duration_ms':n['duration_ms'],'old_midi':n['midi'],
                       'game_views':vs.tolist(),'continuous':detail,'local_midi':int(P[cost.argmin()]),
                       'basic_top':int(np.argmax(bp)+21),'basic_reliability':reliability})
    if not notes:return [],{'policy':'joint-model-event-pitch-v1','notes':[]}
    d=abs(P[:,None]-P[None,:]);trans=.025*d+.015*np.maximum(d-7,0)**2
    costs=np.asarray(costs);score=costs[0].copy();back=np.zeros(costs.shape,np.int16)
    for i in range(1,len(notes)):
        gap=notes[i]['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']
        matrix=score[:,None]+trans*(.2 if gap>350 else 1.)
        back[i]=matrix.argmin(axis=0);score=matrix[back[i],np.arange(len(P))]+costs[i]
    path=np.zeros(len(notes),int);path[-1]=score.argmin()
    for i in range(len(notes)-1,0,-1):path[i-1]=back[i,path[i]]
    out=[]
    for n,k,a in zip(notes,path,audits):
        a['midi']=int(P[k]);out.append({**n,'midi':a['midi']})
    return out,{'policy':'joint-model-event-pitch-v1','notes':audits,'schedule_unchanged':True,
                'reference_lyrics_or_scale_used':False,'changes':sum(a['midi']!=b['midi'] for a,b in zip(notes,out))}
