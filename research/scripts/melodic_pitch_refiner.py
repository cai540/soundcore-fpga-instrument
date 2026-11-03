"""Pitch-only corrections with independent melody-register evidence.

No filename, lyric, editorial score, or hand-corrected note is an input.
The caller's note schedule is immutable. Ambiguous evidence can abstain.
"""
import numpy as np
from vocal_pitch_center import estimate_center
from grounded_pitch_decoder import hz_to_midi, spectral_register, SHIFTS


def interval(n, length):
    a=max(0,(n['start_ms']+9)//10);z=min(length,(n['start_ms']+n['duration_ms']+9)//10)
    trim=min(3,max(0,(z-a)//10))
    return a+trim,z-min(2,trim)


def fit_vowel(n, tracks):
    fits=[]
    for raw,weight in tracks:
        a,z=interval(n,len(raw));x=raw[a:z];w=weight[a:z].copy()
        alternatives=x[:,None]+SHIFTS[None,:]
        k=np.argmin(abs(alternatives-n['midi']),axis=1)
        folded=alternatives[np.arange(len(x)),k]
        w[(x<24)|(abs(folded-n['midi'])>3)|(w<.35)]=0
        fits.append(estimate_center(np.arange(a,z)*.01,folded,w))
    return fits


def pitch_class_evidence(notes,tracks):
    """Use only stable, concordant acoustic intervals to learn a soft prior.

    A prior is used for broad-vibrato ambiguity only, never stable chromatics.
    It is not a prescribed seven-note mask or an assumed major/minor key.
    """
    hist=np.ones(12)*.6;accepted=0
    for n in notes:
        stats=[]
        for raw,w in tracks:
            a,z=interval(n,len(raw));v=raw[a:z];v=v[(v>24)&(w[a:z]>.5)]
            if len(v)<8:break
            center=float(np.median(v));spread=float(np.quantile(v,.8)-np.quantile(v,.2))
            stats.append((center,spread))
        if len(stats)!=len(tracks):continue
        centers=np.array([p for p,_ in stats])
        # Fold relative to the first source without introducing the halfway
        # pitch that an arithmetic average of two octaves would create.
        aligned=centers[0]+(centers-centers[0]+6)%12-6
        if np.ptp(aligned)>.28 or max(v for _,v in stats)>.42:continue
        c=float(np.mean(aligned));nearest=round(c)
        if abs(c-nearest)>.28:continue
        hist[nearest%12]+=min(n['duration_ms']/1000,1.2);accepted+=1
    prior=hist/max(hist.max(),1.)
    return prior,{'stable_intervals':accepted,'relative_pitch_class_support':prior.tolist()}


def refine(notes,pcm,rmvpe,pesto,pesto_conf,melodia_f0):
    """Return a candidate and explicit per-note acceptance/abstention reasons."""
    r=hz_to_midi(rmvpe);p=np.asarray(pesto,float);pc=np.asarray(pesto_conf,float)
    m=hz_to_midi(melodia_f0)
    tracks=[(r,np.where(r>24,1.,0.)),(p,pc)]
    prior,prior_info=pitch_class_evidence(notes,tracks)
    result=[];audits=[]
    for n in notes:
        original=int(n['midi']);pitch=original;reasons=[]
        a,z=interval(n,min(len(r),len(p),len(m)));v=m[a:z];voiced=v[v>24]
        register_info={'voiced_fraction':len(voiced)/max(1,z-a)}
        if len(voiced)>=15 and len(voiced)>=.65*(z-a):
            candidates=np.array([original-12,original,original+12])
            density=np.array([np.mean(abs(voiced-q)<.9) for q in candidates])
            j=int(np.argmax(density));target=int(candidates[j]);register_info.update(target=target,support=density.tolist())
            if target!=original and density[j]>.65 and density[j]-density[1]>.4 and 24<=target<=108:
                # The melody tracker alone cannot promote a residual harmonic.
                # Require an independent tracker hint or a measured harmonic
                # family advantage at the actual source-waveform frequency.
                hints=[]
                for raw,w in tracks:
                    x=raw[a:z];valid=(x>24)&(w[a:z]>.5)
                    hints.append(float(np.mean(abs(x[valid]-target)<1.)) if valid.any() else 0.)
                differences=[]
                for k in range(a,z,max(5,(z-a)//10)):
                    anchor=m[k]
                    if anchor<24:continue
                    family=spectral_register(pcm,k,float(anchor))
                    targets=[s for f,s in family if abs(f-target)<2]
                    currents=[s for f,s in family if abs(f-original)<2]
                    if targets and currents:differences.append(max(targets)-max(currents))
                advantage=float(np.median(differences)) if differences else 0.
                register_info.update(independent_tracker_support=hints,spectral_advantage=advantage)
                if max(hints)>.35 or advantage>.12:
                    pitch=target;reasons.append('corroborated_melody_register')
        fits=fit_vowel({**n,'midi':pitch},tracks)
        if all(f.get('vibrato') for f in fits):
            centers=[f['center'] for f in fits]
            # Broad, periodic modulation must be confirmed in both sources.
            # Stable nonperiodic semitones are never scale-snapped here.
            if (max(centers)-min(centers)<.35 and min(f['explained'] for f in fits)>.7
                and max(f['frequency_hz'] for f in fits)-min(f['frequency_hz'] for f in fits)<1.25):
                center=float(np.mean(centers));amp=float(np.mean([f['amplitude_semitones'] for f in fits]))
                options=np.arange(pitch-1,pitch+2)
                sigma=max(.35,min(.7,amp/3))
                cost=((options-center)/sigma)**2
                if prior_info['stable_intervals']>=12:
                    cost+=-.8*np.log(np.maximum(prior[options%12],.025))
                best=int(options[np.argmin(cost)])
                margin=float(np.sort(cost)[1]-np.min(cost))
                # A partial vibrato cycle can fit a mathematically excellent
                # sinusoid whose center is an unsupported neighbouring pitch.
                # If the old class has stable acoustic anchors and the new one
                # has none, retain uncertainty rather than invent a chromatic
                # change. This rule never runs on a stable chromatic note.
                unsupported=(prior_info['stable_intervals']>=12 and prior[best%12]<.2
                             and prior[pitch%12]>.25)
                # Weak rounding near a half-semitone abstains. The source can
                # otherwise supply a clearly different center from a hard label.
                if best!=pitch and margin>.65 and abs(best-center)<.6 and not unsupported:
                    pitch=best;reasons.append('periodic_vowel_center')
        result.append({**n,'midi':pitch})
        audits.append({'start_ms':n['start_ms'],'duration_ms':n['duration_ms'],'old_midi':original,'new_midi':pitch,
                       'reasons':reasons or ['retained_ambiguous_or_concordant'],'melody_register':register_info,'vowel_fits':fits})
    return result,{'policy':'melody-register-and-periodic-center-candidate','prior':prior_info,'notes':audits,
                   'changes':sum(n['midi']!=q['midi'] for n,q in zip(notes,result))}
