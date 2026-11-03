"""Intended-note class and register are inferred as separate decisions.

GAME interval estimates, Basic Pitch polyphonic note probabilities and CREPE
continuous observations all come from the same input waveform. No transcript,
score, song ID or hand-corrected notes are accepted as inference inputs.
"""
import numpy as np
from vocal_pitch_center import estimate_center

def basic_times(count):
    i=np.arange(count)
    # Spotify Basic Pitch's public model clock, including its window offset.
    per_window=(256/22050)*(172-43844/256)+.0018
    return i*256/22050-np.floor(i/172)*per_window

def kernel_classes(values):
    if len(values)<5:return np.zeros(12),False,False
    reference=float(np.median(values));v=reference+(values-reference+6)%12-6
    fit=estimate_center(np.arange(len(v))*.01,v)
    classes=np.arange(12)
    if fit.get('vibrato'):
        d=(classes-fit['center']+6)%12-6;h=np.exp(-.5*(d/.65)**2)
    else:
        d=(classes[:,None]-v+6)%12-6;h=np.exp(-.5*(d/.55)**2).mean(axis=1)
    stable=float(np.quantile(v,.8)-np.quantile(v,.2))<.42
    return h,bool(fit.get('vibrato')),stable

def fuse_notes(notes,contexts,basic,crepe,pesto,tonality):
    times=basic_times(len(basic['note']));bp=np.asarray(basic['note'],float)
    c=np.where(crepe['f0']>0,69+12*np.log2(np.maximum(crepe['f0'],1)/440),0.)
    ca=69+12*np.log2(np.maximum(crepe['argmax_f0'],1)/440)
    allowed=set(tonality['pitch_classes']) if tonality['enabled'] else None
    classes=np.arange(12);out=[];audit=[];bp_rows=[]
    for i,n in enumerate(notes):
        old=n['midi'];start=n['start_ms'];end=start+n['duration_ms'];edge=min(50,n['duration_ms']//8)
        a,z=np.searchsorted(times,[(start+edge)/1000,(end-min(edge,30))/1000])
        scores=np.mean(bp[a:z],axis=0) if z>a else np.zeros(88)
        background=float(np.median(scores));positive=np.maximum(scores-background,0)
        reliability=float(np.clip((scores.max()-background)/.35,0,1))
        pc=np.zeros(12)
        for p in range(21,109):pc[p%12]=max(pc[p%12],positive[p-21])
        pc/=max(float(pc.max()),.001);bp_rows.append(scores)
        a=(start+edge+9)//10;z=min(len(c),(end-min(edge,30)+9)//10)
        v=c[a:z][(crepe['periodicity'][a:z]>.12)&(c[a:z]>24)]
        raw=ca[a:z]
        hc,periodic,stable=kernel_classes(v)
        ha,pa,sa=kernel_classes(raw)
        # Raw and global paths are views of one model, not independent votes.
        tracking=.6*hc+.4*ha
        context=np.asarray([q[i] for q in contexts]);distance=(classes[:,None]-context+6)%12-6
        context_class=np.exp(-.5*(distance/.6)**2).mean(axis=1)
        base=np.exp(-.5*(((classes-old+6)%12-6)/.6)**2)
        combined=1.4*base+.7*context_class+1.6*reliability*pc+.9*tracking
        cost=-np.log(combined+.015)
        if allowed is not None and not (stable and sa):
            cost+=np.array([0. if k in allowed else .8 for k in classes])
        cls=int(np.argmin(cost));margin=float(np.sort(cost)[1]-np.min(cost))
        new=old+int((cls-old+6)%12-6)
        if cls!=old%12 and margin<.10:new=old
        out.append({**n,'midi':new})
        audit.append({'start_ms':start,'duration_ms':n['duration_ms'],'old_midi':old,'class_midi':new,
                      'class_margin':margin,'basic_reliability':reliability,'basic_peak_midi':int(scores.argmax()+21),
                      'class_costs':cost.tolist(),'crepe_periodic':periodic})
    for iteration in range(2):
        previous=[n['midi'] for n in out]
        for i,n in enumerate(out):
            current=n['midi'];options=current+np.array([-24,-12,0,12,24]);scores=bp_rows[i]
            a=(n['start_ms']+9)//10;z=min(len(c),(n['start_ms']+n['duration_ms']+9)//10)
            r=c[a:z];r=r[(r>24)&(crepe['periodicity'][a:z]>.12)]
            p=pesto['midi'][a:z];p=p[pesto['confidence'][a:z]>.5]
            bp_strength=np.array([scores[k-21] if 21<=k<=108 else 0. for k in options])
            support=[]
            for x in [r,p]:support.append(np.array([float(np.mean(abs(x-k)<1.2)) if len(x) else 0. for k in options]))
            support=np.asarray(support);j=int(np.argmax(bp_strength));target=int(options[j])
            reason='retain_register'
            if target!=current and bp_strength[j]>.25 and np.all(support[:,j]>.35):
                n['midi']=target;reason='polyphonic_note_and_two_register_observations'
            elif 0<i<len(out)-1:
                left=previous[i-1];right=previous[i+1]
                gap1=n['start_ms']-out[i-1]['start_ms']-out[i-1]['duration_ms']
                gap2=out[i+1]['start_ms']-n['start_ms']-n['duration_ms']
                exact_octave=abs(current-left)==12 or abs(current-right)==12
                if gap1<250 and gap2<250 and not exact_octave:
                    for j,target in enumerate(options):
                        if abs(target-current)!=12 or not 21<=target<=108:continue
                        old_distance=abs(current-left)+abs(current-right)
                        new_distance=abs(target-left)+abs(target-right)
                        if (max(abs(target-left),abs(target-right))<=6 and old_distance-new_distance>=8
                            and bp_strength[j]>.12 and bp_strength[j]>=bp_strength[2]*.25):
                            n['midi']=int(target);reason='isolated_period_alias_with_polyphonic_evidence';break
            audit[i].update(new_midi=n['midi'],register_reason=reason,register_support=support.tolist(),
                            basic_register_support=bp_strength.tolist())
    return out,{'policy':'separate_note_class_and_register_v1','notes':audit,'schedule_unchanged':True,
                'changes':sum(a['midi']!=b['midi'] for a,b in zip(notes,out)),'reference_used':False,
                'recording_tonality':tonality}
