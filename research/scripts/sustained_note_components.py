"""Recover real sustained components hidden by an overlarge acoustic syllable.

This is not a melisma budget. A second component must last at least 220 ms,
have a second independent pitch observation and trained note-activity support.
Short vibrato fluctuations cannot create new attacks. No score is loaded.
"""
import numpy as np
from scipy.ndimage import median_filter
from note_probability_fusion import basic_times


def _runs(values):
    edges=np.r_[0,np.flatnonzero(values[1:]!=values[:-1])+1,len(values)]
    return [(int(a),int(z),int(values[a])) for a,z in zip(edges,edges[1:])]


def recover_components(notes,views,evidence,pesto,basic,tonality):
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    pp=pesto['midi'].astype(float);pc=pesto['confidence'];bt=basic_times(len(basic['note']));bp=basic['note'].astype(float)
    allowed=set(tonality['pitch_classes']) if tonality['enabled'] else None
    out=[];audits=[]
    for i,n in enumerate(notes):
        old=n['midi'];a=(n['start_ms']+9)//10;z=min(len(pp),(n['start_ms']+n['duration_ms']+9)//10)
        if z-a<55:out.append(dict(n));continue
        raw=np.array([v[i] for v in views]);anchor=old
        bx,by=np.searchsorted(bt,[(a+4)/100,(z-2)/100])
        mean_bp=bp[bx:by].mean(axis=0) if by>bx else np.zeros(88)
        def activity(k):return float(mean_bp[k-21]) if 21<=k<=108 else 0.
        for candidate in [old-12,old+12]:
            # Do not follow a lower-period context error when the trained
            # polyphonic evidence favors the existing melody register.
            if (np.sum(abs(raw-candidate)<1.2)==len(raw) and activity(candidate)>.12
                and activity(candidate)>activity(old)*1.3):anchor=candidate
        p=pp[a:z];valid=pc[a:z]>.5
        if valid.mean()<.5:out.append(dict(n));continue
        # Period aliases are mapped discretely around the complete-note anchor.
        p=anchor+(p-anchor+6)%12-6
        r=anchor+(rm[a:z]-anchor+6)%12-6
        p[~valid]=np.nan
        idx=np.arange(len(p));ok=np.isfinite(p)
        p=np.interp(idx,idx[ok],p[ok])
        smooth=median_filter(p,size=15,mode='nearest')
        choices=np.arange(anchor-6,anchor+7)
        if allowed is not None:choices=np.array([k for k in choices if k%12 in allowed])
        if not len(choices):out.append(dict(n));continue
        labels=choices[np.argmin(abs(smooth[:,None]-choices[None,:]),axis=1)]
        # A continuous chromatic plateau with trained-note support survives.
        rounded_smooth=np.floor(smooth+.5).astype(int)
        for s,e,pitch in _runs(rounded_smooth):
            if e-s<22 or (allowed is not None and pitch%12 in allowed):continue
            x,y=np.searchsorted(bt,[(a+s)/100,(a+e)/100])
            b=bp[x:y,pitch-21].mean() if 21<=pitch<=108 and y>x else 0.
            if np.quantile(p[s:e],.8)-np.quantile(p[s:e],.2)<.35 and b>.3:labels[s:e]=pitch
        # Delete transient islands by duration, retaining the neighboring
        # main note with the stronger whole-island acoustic fit.
        for _ in range(8):
            runs=_runs(labels);short=[(s,e,k,j) for j,(s,e,k) in enumerate(runs) if e-s<22]
            if not short:break
            changed=False
            for s,e,k,j in sorted(short,key=lambda q:q[1]-q[0]):
                neighbors=[runs[t][2] for t in [j-1,j+1] if 0<=t<len(runs)]
                if not neighbors:continue
                chosen=min(neighbors,key=lambda v:float(np.mean(abs(smooth[s:e]-v))))
                labels[s:e]=chosen;changed=True
            if not changed:break
        runs=_runs(labels);accepted=[]
        for s,e,pitch in runs:
            x,y=np.searchsorted(bt,[(a+s+3)/100,(a+e-2)/100])
            b=bp[x:y].mean(axis=0) if y>x else np.zeros(88)
            activity=max([float(b[k-21])+.25*float(b[max(0,k-22)])+.25*float(b[min(87,k-20)])
                          for k in [pitch-12,pitch,pitch+12] if 21<=k<=108]+[0])
            r_good=r[s+3:e-2];r_good=r_good[np.isfinite(r_good)]
            p_good=p[s+3:e-2]
            agreement=float(np.mean(abs(r_good-pitch)<1.3)) if len(r_good) else 0.
            stable=float(np.mean(abs(p_good-pitch)<1.05)) if len(p_good) else 0.
            accepted.append(e-s>=22 and activity>.16 and agreement>.40 and stable>.65)
        distinct=len({k for s,e,k in runs})
        # A one-off attack/glide, or two alternating semitone labels from a
        # broad vibrato, is not enough to split an acoustic syllable.
        real=(len(runs)>=2 and all(accepted) and distinct>=2
              and max(k for s,e,k in runs)-min(k for s,e,k in runs)>=2)
        if real:
            for j,(s,e,pitch) in enumerate(runs):
                start=n['start_ms'] if j==0 else (a+s)*10
                end=n['start_ms']+n['duration_ms'] if j==len(runs)-1 else (a+e)*10
                out.append({**n,'start_ms':start,'duration_ms':end-start,'midi':pitch})
        else:out.append(dict(n))
        audits.append({'start_ms':n['start_ms'],'old_midi':old,'anchor_midi':anchor,
                       'split':bool(real),'components':[{'start_ms':(a+s)*10,'duration_ms':(e-s)*10,'midi':k,'supported':bool(g)}
                               for (s,e,k),g in zip(runs,accepted)]})
    return out,{'policy':'supported-sustained-components-v1','reference_used':False,
                'split_regions':sum(q['split'] for q in audits),'notes_added':len(out)-len(notes),'regions':audits}
