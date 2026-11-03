"""Estimate the center of an actually observed vocal vibrato before rounding.

No lyric, scale/key or target pitch is used. Linear motion alone and flat
multi-note plateaus are not grounds for sinusoidal demodulation.
"""
import numpy as np

def estimate_center(times,pitches,weights=None):
    t=np.asarray(times,float);p=np.asarray(pitches,float)
    w=np.ones(len(p)) if weights is None else np.asarray(weights,float)
    valid=np.isfinite(p)&np.isfinite(t)&(w>0);t=t[valid];p=p[valid];w=w[valid]
    if len(p)<8:return {'center':None,'vibrato':False,'reason':'insufficient'}
    mean=float(np.average(p,weights=w));fallback={'center':mean,'vibrato':False,'reason':'no_periodic_evidence'}
    if len(p)<24 or t[-1]-t[0]<.25:return fallback
    # Integer plateau sequences may repeat, but they are actual notes rather
    # than a continuous oscillating vocal pitch.
    motion=np.mean(abs(np.diff(p))>.025)
    if motion<.45:return fallback
    t=t-(t[0]+t[-1])/2;root=np.sqrt(w);base=np.column_stack([np.ones(len(t)),t])
    linear=np.linalg.lstsq(base*root[:,None],p*root,rcond=None)[0]
    variance=float(np.average((p-base@linear)**2,weights=w))
    if variance<.025:return fallback
    best=None
    for hz in np.arange(3.5,9.01,.25):
        if hz*(t[-1]-t[0])<1.3:continue
        x=np.column_stack([np.ones(len(t)),t,np.sin(2*np.pi*hz*t),np.cos(2*np.pi*hz*t)])
        coef=np.linalg.lstsq(x*root[:,None],p*root,rcond=None)[0]
        error=float(np.average((p-x@coef)**2,weights=w));amplitude=float(np.hypot(coef[2],coef[3]))
        explained=1-error/variance
        train=np.arange(len(t))%2==0
        check=np.linalg.lstsq(x[train]*root[train,None],p[train]*root[train],rcond=None)[0]
        cv=float(np.average((p[~train]-x[~train]@check)**2,weights=w[~train]))
        if explained<.6 or cv>variance*.5 or not .15<=amplitude<=2.5:continue
        if abs(coef[1])*(t[-1]-t[0])>1.5:continue
        score=error+.025*(hz-6)**2
        if best is None or score<best[0]:
            best=(score,{'center':float(coef[0]),'vibrato':True,'frequency_hz':float(hz),
                         'amplitude_semitones':amplitude,'slope':float(coef[1]),'explained':explained,
                         'cross_validated_error':cv,'raw_mean':mean})
    return best[1] if best else fallback
