"""Discrete register recovery backed by complete-note neural contexts.

Continuous F0 trackers can all follow a dominant period alias. Three neural
context views are not three independent models; their agreement must also be
supported by polyphonic note evidence or another pitch family. Clear observed
chromatic notes and genuine octave leaps remain eligible.
"""
import numpy as np
from note_probability_fusion import basic_times


def refine_context_register(notes,views,evidence,pesto,crepe,basic,tonality,motif=None):
    if not notes:return [],{'policy':'context-and-polyphonic-register-v2','notes':[],'changes':0,'reference_used':False,'schedule_unchanged':True}
    times=basic_times(len(basic['note']));bp=np.asarray(basic['note'],float)
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),0.)
    cr=69+12*np.log2(np.maximum(crepe['argmax_f0'],1)/440)
    allowed=set(tonality['pitch_classes']) if tonality['enabled'] else None
    out=[];audit=[]
    for i,n in enumerate(notes):
        old=n['midi'];new=old;reasons=[];raw=np.array([v[i] for v in views])
        a=(n['start_ms']+9)//10;z=min(len(rm),(n['start_ms']+n['duration_ms']+9)//10)
        trim=min(4,(z-a)//7);s=a+trim;e=z-min(2,trim)
        r=rm[s:e];r=r[r>24];p=pesto['midi'][s:e][pesto['confidence'][s:e]>.5]
        c=cr[s:e][crepe['periodicity'][s:e]>.15]
        x,y=np.searchsorted(times,[s/100,e/100]);b=bp[x:y].mean(axis=0) if y>x else np.zeros(88)
        def prob(k):return float(b[k-21]) if 21<=k<=108 else 0.
        def support(v,k):return float(np.mean(abs(v-k)<1.5)) if len(v) else 0.
        # A categorical vote chooses an octave; octave values are never averaged.
        options=old+np.array([-24,-12,0,12,24]);counts=[np.sum(abs(raw-k)<1.) for k in options]
        j=int(np.argmax(counts));target=int(options[j])
        if (target!=old and counts[j]>=2 and abs(target-old)==12 and prob(target)>.08
            and (max(support(v,target) for v in [r,p,c])>.12 or counts[j]==3)):
            new=target;reasons.append('context_register_with_same_audio_support')
        # Detect a local subharmonic detour with actual alternate note activity.
        if new==old and 0<i<len(notes)-1:
            left=notes[i-1];right=notes[i+1]
            gaps=[n['start_ms']-left['start_ms']-left['duration_ms'],right['start_ms']-n['start_ms']-n['duration_ms']]
            if max(gaps)<250:
                for target in [old-12,old+12]:
                    distance=max(abs(target-left['midi']),abs(target-right['midi']))
                    gain=abs(old-left['midi'])+abs(old-right['midi'])-abs(target-left['midi'])-abs(target-right['midi'])
                    if (distance<=5 and gain>=10 and prob(target)>.22 and prob(target)>=prob(old)*.6
                        and abs(old-left['midi'])!=12 and abs(old-right['midi'])!=12):
                        new=target;reasons.append('local_period_alias_with_strong_polyphonic_alternative');break
        # Joint register observations recover a block even if the neural F0
        # context views share a low-period mistake. Require two model families.
        if new==old:
            for target in [old-12,old+12]:
                if (prob(target)>.25 and prob(target)>=prob(old)*.8 and support(p,target)>.45
                    and support(c,target)>.18 and not np.all(abs(raw-old)<1.)):
                    new=target;reasons.append('polyphonic_and_continuous_register_agreement');break
        if new!=old:
            # Whole-syllable decoding has already repaired many period aliases.
            # Do not undo those repairs merely because local F0 agrees low.
            neighbors=[]
            if i and n['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']<350:neighbors.append(notes[i-1]['midi'])
            if i+1<len(notes) and notes[i+1]['start_ms']-n['start_ms']-n['duration_ms']<350:neighbors.append(notes[i+1]['midi'])
            old_variation=sum(abs(old-k) for k in neighbors);new_variation=sum(abs(new-k) for k in neighbors)
            repeat_support=False
            if motif and max(prob(old),prob(new))<.16:
                entry=motif['notes'][i]
                repeat_support=any(v['midi']==new and v['matched_notes']>=16 and v['strength']>.7 for v in entry['evidence'])
            true_octave=any(abs(old-k)==12 for k in neighbors) and prob(old)>.2 and prob(old)>prob(new)*1.15
            if true_octave:
                new=old;reasons=['preserve_supported_exact_octave_jump']
            elif not neighbors and not repeat_support:
                new=old;reasons=['retain_whole_syllable_register_over_local_period_alias']
        if allowed is not None and new%12 not in allowed:
            folded=[];spreads=[]
            for v in [r,p,c]:
                v=new+(v-new+6)%12-6
                if len(v)>=6:
                    folded.append(float(np.median(v)));spreads.append(float(np.quantile(v,.8)-np.quantile(v,.2)))
            # A truly stable chromatic note bypasses inferred scale correction.
            clear=n['duration_ms']>=400 and prob(new)>.3 and len(spreads)>=2 and sum(q<.35 for q in spreads)>=2
            near=[k for k in range(new-1,new+2) if k%12 in allowed]
            if not clear and near and len(folded)>=2:
                context_center=float(np.median(new+(raw-new+6)%12-6))
                center=.6*float(np.median(folded))+.4*context_center
                target=min(near,key=lambda k:abs(center-k))
                context_class=np.mean(abs((raw-target+6)%12-6)<1.)
                if abs(center-target)<1.05 and context_class>=.66:
                    new=target;reasons.append('ambiguous_intonation_in_recording_pitch_collection')
        out.append({**n,'midi':int(new)})
        audit.append({'start_ms':n['start_ms'],'old_midi':old,'new_midi':int(new),'context_midi':raw.tolist(),
                      'reasons':reasons or ['retain'],'basic_old':prob(old),'basic_new':prob(new)})
    # Resolve neighboring proposals together. Choosing each alias against the
    # still-uncorrected neighbors can make two adjacent errors reinforce one
    # another. The original complete-syllable decision remains the default.
    candidates=np.array([[n['midi'],q['midi']] for n,q in zip(notes,out)])
    emissions=np.zeros((len(notes),2));back=np.zeros((len(notes),2),int)
    for i,entry in enumerate(audit):
        if candidates[i,0]==candidates[i,1]:emissions[i,1]=1e4;continue
        emissions[i,1]=.9-.6*np.log((entry['basic_new']+.08)/(entry['basic_old']+.08))
        if abs(candidates[i,1]-candidates[i,0])<3:emissions[i,1]-=.65
        if motif and max(entry['basic_new'],entry['basic_old'])<.16:
            if any(v['midi']==candidates[i,1] and v['strength']>.7 for v in motif['notes'][i]['evidence']):emissions[i,1]-=2.
    score=emissions[0].copy()
    for i in range(1,len(notes)):
        d=abs(candidates[i-1,:,None]-candidates[i,None,:])
        transition=.035*d+.035*np.maximum(d-5,0)**2
        gap=notes[i]['start_ms']-notes[i-1]['start_ms']-notes[i-1]['duration_ms']
        if gap>350:transition*=.2
        matrix=score[:,None]+transition;back[i]=matrix.argmin(axis=0)
        score=matrix[back[i],np.arange(2)]+emissions[i]
    path=np.zeros(len(notes),int);path[-1]=score.argmin()
    for i in range(len(notes)-1,0,-1):path[i-1]=back[i,path[i]]
    for i,(q,j) in enumerate(zip(out,path)):
        q['midi']=int(candidates[i,j]);audit[i]['proposed_midi']=audit[i]['new_midi'];audit[i]['new_midi']=q['midi']
        audit[i]['sequence_accepted']=bool(j)
    return out,{'policy':'context-and-polyphonic-register-v2','reference_used':False,'schedule_unchanged':True,
                'changes':sum(n['midi']!=q['midi'] for n,q in zip(notes,out)),'notes':audit,'tonality':tonality}
