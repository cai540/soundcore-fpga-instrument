"""Pitch evidence for trained note boundaries, independent of song identities.

The note classifier and the continuous F0 tracker solve different problems.
Use the central voiced F0 only when it supplies enough measured evidence;
leave learned boundaries, rests and repeated attacks untouched.
"""
import numpy as np


def f0_grid(trace, length_ms):
    """Place context-window F0 back on the 10 ms source clock, core only."""
    result=np.zeros((length_ms+9)//10,dtype=float)
    for c in trace['chunks']:
        a=c['core_start_ms'];z=c['core_end_ms'];begin=c['begin_ms']
        k=np.arange((a+9)//10,min((z+9)//10,len(result)))
        f=np.array(c['f0'],dtype=float)
        # Nearest native 10ms sample; no cumulative duration rounding.
        j=np.clip(np.rint((k*10-begin)/10).astype(int),0,len(f)-1)
        result[k]=f[j]
    return result


def central_pitch(notes, f0):
    out=[];audit=[]
    for n in notes:
        start=n['start_ms'];end=start+n['duration_ms']
        edge=min(60,n['duration_ms']*.15)
        a=int(np.ceil((start+edge)/10));z=int(np.floor((end-edge)/10))
        samples=f0[a:z];voiced=samples[samples>0]
        q=dict(n)
        evidence={'start_ms':start,'model_midi':n['midi'],'voiced_frames':len(voiced),'frames':len(samples)}
        if len(voiced)>=6 and len(voiced)>=len(samples)*.55:
            pitches=69+12*np.log2(voiced/440)
            center=float(np.median(pitches))
            target=int(np.floor(center+.5))
            evidence.update(center_midi=center,iqr_semitones=float(np.quantile(pitches,.75)-np.quantile(pitches,.25)))
            # An interval with a genuine glissando or mixed notes is ambiguous;
            # its median must not overwrite the trained classifier.
            if evidence['iqr_semitones']<=1.5 and abs(target-n['midi'])<=2:
                q['midi']=target
        evidence['output_midi']=q['midi'];audit.append(evidence);out.append(q)
    return out,audit
