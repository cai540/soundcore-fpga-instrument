"""Syllable-first reduction of singing, using acoustic evidence only.

An estimated syllable normally emits one main pitch. Repeated syllables keep
separate attacks even at the same pitch. A bounded number of well-supported,
sustained two-plateau ornaments can be retained; no note-count/song template.
"""
import numpy as np
from scipy.ndimage import median_filter,maximum_filter1d
from scipy.signal import find_peaks

PITCHES=np.arange(24,101)

def runs(a):
    edges=np.r_[0,np.flatnonzero(a[1:]!=a[:-1])+1,len(a)]
    return [(int(s),int(e),a[s]) for s,e in zip(edges,edges[1:])]

def acoustic_features(pcm):
    """10ms source grid; gain-normalized coarse timbre and harmonic support."""
    T=(len(pcm)//16+9)//10;pad=np.pad(pcm,(512,512))
    frames=np.lib.stride_tricks.sliding_window_view(pad,1024)[::160][:T]
    hann=np.hanning(1024);rms=np.sqrt(np.mean(frames.astype(float)**2,axis=1))
    harmony=np.zeros((T,len(PITCHES)),np.float32);timbre=np.zeros((T,24),np.float32)
    octave_penalty=np.zeros_like(harmony)
    hz=440*2**((PITCHES-69)/12);bins=np.geomspace(100,7900,26)*2048/16000
    for a in range(0,T,400):
        z=min(T,a+400);s=np.abs(np.fft.rfft(frames[a:z]*hann,n=2048))
        floor=median_filter(s,size=(1,31),mode='nearest')+np.max(s,axis=1,keepdims=True)*.001+1e-9
        white=np.log1p(s/floor);near=maximum_filter1d(white,size=5,axis=1,mode='nearest')
        weight_sum=np.zeros(len(PITCHES));acc=np.zeros((z-a,len(PITCHES)))
        raw_near=maximum_filter1d(np.maximum(0,s-floor),size=5,axis=1,mode='nearest')
        odd=np.zeros_like(acc);even=np.zeros_like(acc)
        # Harmonic product style: a half-frequency candidate pays for missing
        # odd partials. This is evidence, never an unconditional octave lift.
        for h in range(1,7):
            k=np.rint(hz*h*2048/16000).astype(int);valid=k<1024;w=1/np.sqrt(h)
            acc[:,valid]+=near[:,k[valid]]*w;weight_sum[valid]+=w
            (odd if h%2 else even)[:,valid]+=raw_near[:,k[valid]]**2*w
        harmony[a:z]=acc/np.maximum(weight_sum,1e-6)
        fraction=odd/np.maximum(odd+even,1e-15)
        octave_penalty[a:z]=np.clip((.08-fraction)/.08,0,1)*2.8
        for b in range(24):
            x=int(bins[b]);y=max(x+1,int(bins[b+2]));timbre[a:z,b]=np.sum(s[:,x:y]**2,axis=1)
    timbre/=np.maximum(timbre.sum(axis=1,keepdims=True),1e-12)
    flux=np.r_[0,np.sum(np.maximum(0,np.diff(timbre,axis=0)),axis=1)]
    return {'rms':rms,'flux':maximum_filter1d(flux,9),'harmonic':harmony,'octave_penalty':octave_penalty}

def dense(notes,T):
    out=np.zeros(T,np.float32)
    for n in notes:
        a=max(0,(n['start_ms']+9)//10);z=min(T,(n['start_ms']+n['duration_ms']+9)//10)
        out[a:z]=n['midi']
    return out

def midi(f):return np.where(f>0,69+12*np.log2(np.maximum(f,1)/440),0)

def mode_pitch(x):
    x=x[x>0]
    if len(x)<5:return 0,0.
    h=np.exp(-.5*((PITCHES[:,None]-x)/.55)**2).sum(axis=1)
    k=int(np.argmax(h));return int(PITCHES[k]),float(h[k]/len(x))

def decode_syllables(pcm,evidence,game_notes,features=None,allow_ornaments=True):
    ms=len(pcm)//16;T=(ms+9)//10
    f=acoustic_features(pcm) if features is None else features
    rms=f['rms'][:T];flux=f['flux'][:T];harm=f['harmonic'][:T]
    rp=midi(evidence['rmvpe'][:T]);fp=midi(evidence['fcpe'][:T]);conf=evidence['fcpe_confidence'][:T]
    word=evidence['word'][:T];gp=dense(game_notes,T)
    floor=max(1e-5,float(np.quantile(rms,.9))*.02)
    near_voice=maximum_filter1d((gp>0).astype(float),11)>.5
    active=(rms>floor)&((rp>0)|((fp>0)&(conf>.06)))&(near_voice|(conf>.65))
    # A weak, recording-derived pitch-class prior resolves ambiguous adjacent
    # semitones. It is not a supplied key or a seven-note mask: clear rare and
    # chromatic tones keep their acoustic likelihood advantage.
    reliable=active&(gp>0)&(rp>0)&(abs(rp-gp)<.35)
    class_hist=np.bincount(np.rint(gp[reliable]).astype(int)%12,minlength=12).astype(float)
    class_prior=-.25*np.log((class_hist+max(1.,class_hist.max()*.05))/(max(1.,class_hist.max())*1.05))
    # Only fill short pitch dropouts while an independent note model says the
    # sound continues and energy remains audible. Do not bridge true silence.
    for a,z,state in runs(active):
        if not state and 0<a<z<T and z-a<=10 and np.all(rms[a:z]>floor*1.3) and np.mean(gp[a:z]>0)>.8:
            active[a:z]=True
    # A faint, pitched separation tail is not a new syllable. Trim only the
    # edges of voiced islands relative to their own level, not quiet words
    # inside a phrase and not a recording-wide maximum.
    for a,z,state in runs(active):
        if not state:continue
        audible=np.flatnonzero(rms[a:z]>=max(floor,float(np.quantile(rms[a:z],.85))*.12))
        if len(audible):
            active[a:a+max(0,int(audible[0])-2)]=False
            active[min(z,a+int(audible[-1])+4):z]=False
    peaks,_=find_peaks(word,height=.5,prominence=.18,distance=10)
    # GAME onset is only supplemental: it needs nearby phonetic evidence and
    # two stable pitch plateaus, so a vibrato crossing is not an extra onset.
    supplements=[];stable_note_boundaries=[]
    for n in game_notes[1:]:
        k=round(n['start_ms']/10)
        if k<14 or k>=T-14:continue
        l,lc=mode_pitch(rp[max(0,k-22):k-3]);r,rc=mode_pitch(rp[k+3:min(T,k+24)])
        wpeak=float(np.max(word[max(0,k-8):k+9]))
        gl,gc=mode_pitch(gp[max(0,k-26):k-3]);gr,gd=mode_pitch(gp[k+3:min(T,k+24)])
        sustained=(gl>0 and gr>0 and 1<=abs(gl-gr)<=24 and gc>.52 and gd>.78 and n['duration_ms']>=280
                   and (wpeak>.12 or flux[k]>.065))
        # A trained note model can split one real plateau into adjacent
        # semitones. Detect the sustained continuous-F0 step as well, rather
        # than requiring either corrupted fragment to be long on its own.
        lv=rp[max(0,k-24):k-3];rv=rp[k+3:min(T,k+28)]
        lv=lv[lv>0];rv=rv[rv>0]
        stable_f0=(len(lv)>=12 and len(rv)>=18 and abs(np.median(lv)-np.median(rv))>=1.25
                   and np.quantile(lv,.75)-np.quantile(lv,.25)<.8
                   and np.quantile(rv,.75)-np.quantile(rv,.25)<.8)
        phonetic_recovery=(gl>0 and gr>0 and gl!=gr and gc>.7 and gd>.6 and wpeak>.35
                           and flux[k]>.14 and n['duration_ms']>=140)
        sustained=sustained or stable_f0 or phonetic_recovery
        if sustained:stable_note_boundaries.append(k)
        if (sustained or (l and r and l!=r and lc>.65 and rc>.65 and wpeak>.22 and flux[k]>.09)):
            if not len(peaks) or np.min(abs(peaks-k))>=10:supplements.append(k)
    all_peaks=sorted(set(peaks.tolist()+supplements))
    syllables=[];boundary_audit=[]
    for a,z,state in runs(active):
        if not state or z-a<8:continue
        if np.mean(conf[a:z]>.06)<.15 and np.mean(gp[a:z]>0)<.8:continue
        candidates=[k for k in all_peaks if a+8<=k<=z-8]
        cuts=[a]
        for k in candidates:
            # A word detector can fire on vowel vibrato too. Such a cut needs
            # phonetic change, a stable pitch change or a very strong word peak.
            lp,lc=mode_pitch(rp[max(a,k-20):k]);rr,rc=mode_pitch(rp[k:min(z,k+20)])
            strong=word[k]>.94
            real_change=lp>0 and rr>0 and lp!=rr and lc>.6 and rc>.6
            phonetic=flux[k]>.12
            note_boundary=any(abs(k-t)<=10 for t in stable_note_boundaries)
            accept=strong or phonetic or real_change or note_boundary
            # Same sustained vowel may fool the word network during vibrato.
            # Repeated equal-pitch words need a phonetic or amplitude attack.
            left_peak=float(np.max(rms[max(a,k-16):k]));right_peak=float(np.max(rms[k:min(z,k+16)]))
            valley=float(np.min(rms[max(a,k-3):min(z,k+4)]))
            amplitude_attack=valley<min(left_peak,right_peak)*.45
            if lp==rr and lp>0 and not phonetic and not amplitude_attack and word[k]<.995:accept=False
            # Closely spaced candidates compete unless both have independent,
            # clear phonetic attacks. This is not a global minimum note length.
            if accept and k-cuts[-1]<20 and cuts[-1]!=a:
                prev=cuts[-1]
                if not(flux[k]>.22 and flux[prev]>.22 and min(word[k],word[prev])>.8):
                    if word[k]+flux[k]>word[prev]+flux[prev]:cuts[-1]=k
                    accept=False
            if accept:cuts.append(k)
            boundary_audit.append({'ms':int(k*10),'accepted':bool(accept),'word_probability':float(word[k]),'flux':float(flux[k])})
        cuts.append(z)
        # Reject a tiny unsupported cell between boundary peaks. Real fast
        # syllables with strong phonetic attacks remain eligible down to 80ms.
        j=1
        while j<len(cuts)-1:
            k=cuts[j]
            if min(k-cuts[j-1],cuts[j+1]-k)<20 and not(word[k]>.9 and flux[k]>.2):
                cuts.pop(j)
            else:j+=1
        for x,y in zip(cuts,cuts[1:]):
            if y-x>=8:syllables.append((x,y))
    if not syllables:return [],{'syllables':[],'ornaments_retained':0,'boundaries':boundary_audit}

    def pitch_evidence(a,z):
        trim=min(6,(z-a)//6);x=a+trim;y=z-min(3,trim)
        q=np.maximum(rms[x:y]/max(float(np.quantile(rms[a:z],.8)),floor),.05).clip(0,1)
        vote=np.zeros(len(PITCHES))
        # Learned interval pitch contributes strongly, while voiced F0 refines
        # it within a syllable instead of averaging across several syllables.
        for p,w in [(gp,1.15),(rp,.85),(fp,.25)]:
            v=p[x:y];valid=v>0
            if np.any(valid):
                delta=np.abs(np.diff(v,prepend=v[0]));steady=1/(1+(delta/.4)**2)
                weights=q[valid]*(.3+.7*steady[valid])
                h=np.exp(-.5*((PITCHES[:,None]-v[valid])/.55)**2)@weights
                vote+=w*h/max(float(weights.sum()),1e-6)
        # Relative harmonic support mainly disambiguates register. Small
        # spectral differences cannot alone force a semitone replacement.
        hs=np.average(harm[x:y],axis=0,weights=q)
        vote=np.maximum(vote,1e-4)
        # Allow octave alternatives when the spectrum supports them, at a cost.
        for shift in [12,-12]:
            moved=np.roll(vote,shift);moved[:max(0,shift)]=0
            if shift<0:moved[shift:]=0
            vote=np.maximum(vote,moved*.25)
        penalty=np.average(f['octave_penalty'][x:y],axis=0,weights=q)
        costs=-np.log(vote+.015)-.6*(hs-np.median(hs))+penalty+class_prior[PITCHES%12]
        return costs,hs

    costs=[];spec=[]
    for a,z in syllables:
        c,h=pitch_evidence(a,z);costs.append(c);spec.append(h)
    costs=np.array(costs);back=np.zeros(costs.shape,np.int16);score=costs[0].copy()
    distances=abs(PITCHES[:,None]-PITCHES[None,:])
    transition=.035*distances+.10*np.maximum(0,distances-7)
    for i in range(1,len(syllables)):
        # New phrases reset continuity; a real melodic octave is not forbidden.
        gap=syllables[i][0]-syllables[i-1][1]
        matrix=score[:,None]+transition*(.15 if gap>=25 else 1.)
        back[i]=np.argmin(matrix,axis=0);score=matrix[back[i],np.arange(len(PITCHES))]+costs[i]
    path=np.zeros(len(syllables),int);path[-1]=int(np.argmin(score))
    for i in range(len(path)-1,0,-1):path[i-1]=back[i,path[i]]
    pitches=PITCHES[path]
    # At most one sustained ornament within a detected syllable, and a small
    # global budget. Short jitter/runs cannot consume it.
    proposals=[]
    if allow_ornaments:
        for i,(a,z) in enumerate(syllables):
            if z-a<70:continue
            for n in game_notes:
                k=round(n['start_ms']/10)
                if k-a<24 or z-k<24:continue
                l,lc=mode_pitch(rp[a+4:k-3]);r,rc=mode_pitch(rp[k+3:z-3])
                if l and r and 2<=abs(l-r)<=7 and lc>.72 and rc>.72:
                    # Both plateaus must also match the learned note evidence.
                    gl,gc=mode_pitch(gp[a:k]);gr,gd=mode_pitch(gp[k:z])
                    if gl==l and gr==r and gc>.75 and gd>.75:
                        proposals.append((min(lc,rc)*min(k-a,z-k),i,k,l,r))
    retained={}
    for merit,i,k,l,r in sorted(proposals,reverse=True):
        if i in retained:continue
        if len(retained)>=len(syllables)//8:break
        retained[i]=(k,l,r)
    out=[];audit=[]
    for i,((a,z),pitch) in enumerate(zip(syllables,pitches)):
        parts=[(a,z,int(pitch))]
        if i in retained:
            k,l,r=retained[i];parts=[(a,k,l),(k,z,r)]
        for x,y,p in parts:
            duration=min(ms,y*10)-x*10
            if duration>0:
                q={'start_ms':x*10,'duration_ms':duration,'midi':p,'confidence':0.0}
                # An octave correction can make a pitch-only split disappear.
                # Merge only such unarticulated, contiguous equal-pitch halves;
                # real same-pitch words and actual rests keep their attacks.
                independent_attack=(word[x]>.9 or flux[x]>.12)
                if out and out[-1]['midi']==p and out[-1]['start_ms']+out[-1]['duration_ms']==x*10 and not independent_attack:
                    out[-1]['duration_ms']+=duration
                else:out.append(q)
        audit.append({'start_ms':a*10,'end_ms':min(ms,z*10),'main_midi':int(pitch),
                      'output_notes':len(parts),'retained_sustained_ornament':i in retained})
    return out,{'syllables':audit,'boundaries':boundary_audit,'ornaments_retained':len(retained),
                'policy':'acoustic_syllable_main_pitch_v6','actual_characters_recognized':False,
                'pitch_trackers':'RWBD boundaries + GAME interval pitch + RMVPE/FCPE + spectral register evidence',
                'confidence_note':'zero means unavailable, not calibrated confidence'}
