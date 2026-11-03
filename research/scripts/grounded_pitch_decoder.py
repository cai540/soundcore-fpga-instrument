"""Pitch-only decoder: continuous observations and source-waveform register.

The note schedule is immutable. No lyrics, old scores, song names or target
key enter pitch selection. Vibrato is integrated in cents before quantizing.
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.special import logsumexp

PITCHES=np.arange(1,128,dtype=float)
SHIFTS=np.array([0.,-12.,12.,-19.01955,19.01955])
ALIAS_COST=np.array([0.,.38,.38,.7,.7])

def hz_to_midi(f):return np.where(f>0,69+12*np.log2(np.maximum(f,1)/440),0)

def spectral_register(pcm,k,anchor):
    """Compare measured harmonic families at their continuous frequencies.
    Candidate semitone labels share a register score: the spectrum must not
    pull a flat/vibrating note onto a stronger neighbouring integer FFT bin.
    """
    center=k*160;start=center-1024;end=center+1024;x=np.zeros(2048)
    a=max(0,start);z=min(len(pcm),end)
    if z>a:x[a-start:z-start]=pcm[a:z]
    mag=np.abs(np.fft.rfft(x*np.hanning(2048),n=8192));envelope=gaussian_filter1d(mag,32)
    white=np.log1p(mag/np.maximum(envelope,mag.max()*.01+1e-12));freq=np.arange(len(mag))*16000/8192
    out=[]
    for shift in SHIFTS:
        c=anchor+shift
        if not 24<=c<=108:continue
        grid=c+np.arange(-.4,.4001,.08);hz=440*2**((grid-69)/12)
        harm=np.zeros(len(grid));off=np.zeros(len(grid));weights=0
        for h in range(1,9):
            w=1/np.sqrt(h);weights+=w
            harm+=w*np.interp(h*hz,freq,white,left=0,right=0)
            off+=w*np.interp((h-.5)*hz,freq,white,left=0,right=0)
        scores=(harm-.4*off)/weights
        j=int(np.argmax(scores));out.append((float(grid[j]),float(scores[j])))
    return out

def refine_pitch_schedule(pcm,notes,evidence,pesto,world=None,register_cache=None):
    """Return identical starts/durations with new pitches plus an audit."""
    if not notes:return [],{'policy':'grounded-continuous-pitch-v1','notes':[]}
    T=(len(pcm)//16+9)//10
    rp=hz_to_midi(evidence['rmvpe'][:T]);pp=np.asarray(pesto['midi'][:T],float)
    pc=np.asarray(pesto['confidence'][:T],float)
    wp=hz_to_midi(world['f0'][:T]) if world is not None else np.zeros(T)
    # Short energy windows supply gain weights, not pitch labels.
    pad=np.pad(pcm,(160,160));windows=np.lib.stride_tricks.sliding_window_view(pad,320)[::160][:T]
    rms=np.sqrt(np.mean(windows.astype(float)**2,axis=1));costs=[];audits=[]
    if register_cache is None:register_cache={}
    for n in notes:
        a=max(0,(n['start_ms']+9)//10);z=min(T,(n['start_ms']+n['duration_ms']+9)//10)
        trim=min(5,max(0,(z-a)//8));s=a+trim;e=z-min(trim,3)
        observations=[];weights=[]
        energy=np.clip(rms[s:e]/max(float(np.quantile(rms[a:z],.8)),1e-6),.05,1)
        for values,weight,validity in [(pp,1.,pc>.35),(rp,.85,rp>0),(wp,.35,wp>0)]:
            valid=validity[s:e]&np.isfinite(values[s:e])&(values[s:e]>24)
            observations.extend(values[s:e][valid].tolist());weights.extend((energy[valid]*weight).tolist())
        if not observations:
            c=np.minimum(abs(PITCHES-n['midi']),3.)*3;costs.append(c);audits.append({'fallback_no_voiced_evidence':True});continue
        x=np.asarray(observations);w=np.asarray(weights);w/=w.sum()
        # Compare the whole vowel, not only frames with momentarily flat F0.
        # That old weighting made hard classifier labels beat real vibrato.
        residual=x[None,:,None]+SHIFTS[None,None,:]-PITCHES[:,None,None]
        absolute=abs(residual)
        fit=np.where(absolute<=1.5,residual**2,3*absolute-2.25)
        fit=np.minimum(fit,8)+ALIAS_COST[None,None,:]
        per_observation=np.min(fit,axis=2)
        cost=per_observation@w
        # The source spectrum only selects register/family, independently of
        # semitone quantization. Cache per-frame source evidence for later use.
        spectral=[]
        for k in range(s,e,5):
            anchor=pp[k] if pc[k]>.35 else rp[k]
            if not np.isfinite(anchor) or anchor<=24:continue
            key=str(k)
            if key not in register_cache:register_cache[key]=spectral_register(pcm,k,float(anchor))
            family=register_cache[key]
            if not family:continue
            center=np.array([q[0] for q in family]);score=np.array([q[1] for q in family])
            # All neighbouring semitone labels use one physical family score.
            distance=abs(PITCHES[:,None]-center[None,:])
            nearest=np.argmin(distance,axis=1);good=distance[np.arange(len(PITCHES)),nearest]<4
            value=np.zeros(len(PITCHES));value[good]=score[nearest[good]]
            spectral.append(value)
        if spectral:
            support=np.median(np.array(spectral),axis=0)
            cost-=1.6*(support-np.median(support))
        else:support=np.zeros(len(PITCHES))
        costs.append(cost);audits.append({'old_midi':n['midi'],'observed_frames':len(x),
              'source_midi_mean':float(np.average(x,weights=w)),'spectral_frames':len(spectral),
              'local_best_midi':int(PITCHES[np.argmin(cost)])})
    costs=np.array(costs);dist=abs(PITCHES[:,None]-PITCHES[None,:])
    transition=.035*dist+.13*np.maximum(dist-7,0)
    # Strong physical evidence still allows a real leap. Same-pitch pooling
    # and note deletions are deliberately absent from this pitch-only stage.
    back=np.zeros(costs.shape,np.int16);score=costs[0].copy()
    for i in range(1,len(notes)):
        gap=notes[i]['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']
        matrix=score[:,None]+transition*(.25 if gap>=250 else 1.)
        back[i]=np.argmin(matrix,axis=0);score=matrix[back[i],np.arange(len(PITCHES))]+costs[i]
    path=np.zeros(len(notes),int);path[-1]=int(np.argmin(score))
    for i in range(len(path)-1,0,-1):path[i-1]=back[i,path[i]]
    out=[]
    for n,j,audit in zip(notes,path,audits):
        pitch=int(PITCHES[j]);out.append({**n,'midi':pitch})
        audit.update(start_ms=n['start_ms'],duration_ms=n['duration_ms'],old_midi=n['midi'],new_midi=pitch)
    return out,{'policy':'grounded-continuous-pitch-v1','notes':audits,'changed':sum(a['midi']!=b['midi'] for a,b in zip(notes,out)),
                'timing_changed':False,'reference_or_lyrics_used':False}

def refine_pitch_schedule_guarded(pcm,notes,evidence,pesto,world=None,register_cache=None):
    """Corroborated pitch repairs, with explicit reasons and abstention.

    Separate continuous note center from register. Do not let a stationary
    hard label outweigh a real, continuously vibrating F0 observation.
    """
    T=(len(pcm)//16+9)//10;rp=hz_to_midi(evidence['rmvpe'][:T])
    pp=np.asarray(pesto['midi'][:T],float);pc=np.asarray(pesto['confidence'][:T],float)
    wp=hz_to_midi(world['f0'][:T]) if world is not None else np.zeros(T)
    pad=np.pad(pcm,(160,160));frames=np.lib.stride_tricks.sliding_window_view(pad,320)[::160][:T]
    rms=np.sqrt(np.mean(frames.astype(float)**2,axis=1));out=[];audit=[]
    if register_cache is None:register_cache={}
    def folded_center(v,n):
        if not len(v):return None
        aliases=v[:,None]+SHIFTS[None,:]
        k=np.argmin(abs(aliases-n),axis=1);aligned=aliases[np.arange(len(v)),k]
        aligned=aligned[abs(aligned-n)<3]
        if len(aligned)<5:return None
        low,high=np.quantile(aligned,[.1,.9]);trimmed=aligned[(aligned>=low)&(aligned<=high)]
        return float(np.mean(trimmed))
    for i,n in enumerate(notes):
        a=max(0,(n['start_ms']+9)//10);z=min(T,(n['start_ms']+n['duration_ms']+9)//10)
        edge=min(4,(z-a)//7);s=a+edge;e=z-min(edge,3);old=n['midi'];reason='retain_uncertain'
        voiced=rms[s:e]>max(1e-5,float(np.max(rms[a:z]))*.06)
        r=rp[s:e][(rp[s:e]>24)&voiced];p=pp[s:e][(pc[s:e]>.65)&voiced]
        w=wp[s:e][(wp[s:e]>24)&voiced]
        tracks=[(r,1.),(p,1.),(w,.6)]
        candidates=old+np.array([0,-12,12,-19.01955,19.01955])
        scores=np.zeros(len(candidates));support=np.zeros(len(candidates),int)
        for values,weight in tracks:
            if len(values)<max(5,(e-s)*.3):continue
            mass=np.mean(np.exp(-.5*((values[:,None]-candidates[None,:])/2)**2),axis=0)
            scores+=weight*mass
            support+=mass>.5
        best=int(np.argmax(scores));register=float(old)
        if best!=0 and support[best]>=2 and scores[best]>scores[0]+.2:
            register=float(candidates[best]);reason='independent_register_support'
        # A brief isolated wrong register can survive in all pitch trackers.
        # A repair needs both melodic anchors, actual upper-register tracker
        # samples and a physically plausible spectral family, never continuity
        # alone. An intentional low fundamental with no such samples stays low.
        if register==old and 0<i<len(notes)-1 and n['duration_ms']<=900:
            left=notes[i-1];right=notes[i+1]
            gap1=n['start_ms']-left['start_ms']-left['duration_ms'];gap2=right['start_ms']-n['start_ms']-n['duration_ms']
            if gap1<250 and gap2<250:
                for shift in [12.,-12.,19.01955,-19.01955]:
                    candidate=old+shift
                    if not 1<=candidate<=127 or max(abs(candidate-left['midi']),abs(candidate-right['midi']))>4:continue
                    hints=[float(np.mean(abs(v-candidate)<2.2)) if len(v) else 0 for v,_ in tracks]
                    if max(hints)<.12 or sorted(hints,reverse=True)[1]<.05:continue
                    evidence_scores=[]
                    for k in range(s,e,5):
                        anchor=pp[k] if pc[k]>.35 else rp[k]
                        if anchor<24:continue
                        if str(k) not in register_cache:register_cache[str(k)]=spectral_register(pcm,k,float(anchor))
                        family=register_cache[str(k)]
                        low=[v for q,v in family if abs(q-old)<3];high=[v for q,v in family if abs(q-candidate)<3]
                        if low and high:evidence_scores.append(max(high)/max(max(low),.05))
                    if len(evidence_scores)>=3 and np.median(evidence_scores)>.65:
                        register=candidate;reason='isolated_register_with_audio_hints';break
        centers=[folded_center(v,register) for v,_ in tracks[:2]]
        good=[v for v in centers if v is not None]
        center=float(np.mean(good)) if good else float(register)
        new=old
        if register!=old:
            new=int(np.floor(center+.5));new=max(1,min(127,new))
        elif len(good)==2 and abs(good[0]-good[1])<.65 and abs(center-old)>=.95:
            # A one-semitone move toward independently corroborated vowel
            # center. Ambiguous intonation within a semitone retains the model.
            new=old+(1 if center>old else -1);reason='corroborated_continuous_center'
        q={**n,'midi':new};out.append(q)
        audit.append({'start_ms':n['start_ms'],'duration_ms':n['duration_ms'],'old_midi':old,'new_midi':new,
                      'reason':reason,'continuous_centers':centers,'register_support':support.tolist(),
                      'register_scores':scores.tolist(),'chosen_register':register})
    return out,{'policy':'guarded-continuous-pitch-v2','notes':audit,'changed':sum(a['midi']!=b['midi'] for a,b in zip(notes,out)),
                'timing_changed':False,'reference_or_lyrics_used':False}
