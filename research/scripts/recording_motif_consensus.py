"""Within-recording recurring-melody evidence, with discrete octave voting.

No reference database, lyrics, song identity or expected melody is accepted.
Local sequence matches tolerate an omitted/repeated note. Register transfer
requires surrounding matched notes to agree on the register offset, so an
intentional whole-phrase octave change remains intact.
"""
import numpy as np
from scipy.ndimage import maximum_filter
from note_probability_fusion import basic_times


def note_features(notes,basic,crepe):
    times=basic_times(len(basic['note']));bp=np.asarray(basic['note'],float)
    cp=69+12*np.log2(np.maximum(crepe['argmax_f0'],1)/440)
    feat=[];prob=[];reliability=[]
    for n in notes:
        a=n['start_ms'];z=a+n['duration_ms'];edge=min(50,n['duration_ms']//8)
        x,y=np.searchsorted(times,[(a+edge)/1000,(z-edge)/1000])
        p=bp[x:y].mean(axis=0) if y>x else np.zeros(88);prob.append(p)
        h=np.array([max(p[k-21] for k in range(21,109) if k%12==c) for c in range(12)])
        h=np.maximum(h-np.median(h),0);h/=max(np.linalg.norm(h),1e-6)
        x=(a+edge+9)//10;y=min(len(cp),(z-edge+9)//10)
        v=cp[x:y];v=v[np.isfinite(v)&(v>24)]
        t=np.exp(-.5*(((np.arange(12)[:,None]-v+6)%12-6)/.6)**2).mean(axis=1) if len(v) else np.zeros(12)
        t/=max(np.linalg.norm(t),1e-6)
        base=np.exp(-.5*(((np.arange(12)-n['midi']+6)%12-6)/.5)**2)
        f=1.5*base+.8*h+.4*t;f/=max(np.linalg.norm(f),1e-6);feat.append(f)
        p0=p[n['midi']-21] if 21<=n['midi']<=108 else 0
        alias=max([p[k-21] for k in (n['midi']-12,n['midi']+12) if 21<=k<=108]+[0])
        reliability.append(float(np.clip(p0/.45,0,1)*np.clip((p0-alias+.1)/.35,0,1)))
    return np.asarray(feat),np.asarray(prob),np.asarray(reliability)


def recurring_paths(notes,features):
    count=len(notes);similarity=features@features.T
    score=np.zeros((count+1,count+1));back=np.zeros((count+1,count+1),np.int8)
    for i in range(1,count+1):
        for j in range(i+1,count+1):
            if notes[j-1]['start_ms']-notes[i-1]['start_ms']<8000:continue
            duration_ratio=abs(np.log(max(100,notes[i-1]['duration_ms'])/max(100,notes[j-1]['duration_ms'])))
            reward=2.5*similarity[i-1,j-1]-1.05-.16*min(duration_ratio,2)
            values=(0,score[i-1,j-1]+reward,score[i-1,j]-.85,score[i,j-1]-.85)
            k=int(np.argmax(values));score[i,j]=values[k];back[i,j]=k
    # Read local maxima, not many duplicated prefixes of the same path.
    maxima=(score==maximum_filter(score,size=7,mode='constant'))&(score>=10)
    paths=[];used=set()
    for i,j in sorted(zip(*np.where(maxima)),key=lambda q:-score[q]):
        pairs=[];a,b=i,j
        while a>0 and b>0 and back[a,b]:
            k=back[a,b]
            if k==1:pairs.append((int(a-1),int(b-1)));a-=1;b-=1
            elif k==2:a-=1
            else:b-=1
        pairs=pairs[::-1]
        if len(pairs)<8:continue
        if (notes[pairs[-1][0]]['start_ms']-notes[pairs[0][0]]['start_ms']<2800
            or notes[pairs[0][1]]['start_ms']<=notes[pairs[-1][0]]['start_ms']):continue
        coverage=np.mean([similarity[x,y]>.70 for x,y in pairs])
        if coverage<.78:continue
        if len({notes[x]['midi']%12 for x,y in pairs})<4:continue
        novel=sum((x,y) not in used for x,y in pairs)
        if novel<len(pairs)*.35:continue
        used.update(pairs);paths.append({'pairs':pairs,'score':float(score[i,j]),'coverage':float(coverage)})
    return paths,similarity


def refine_repeats(notes,basic,crepe):
    if not notes:return [],{'policy':'same-recording-motif-v1','notes':[],'paths':[],'changes':0,'reference_used':False,'schedule_unchanged':True}
    f,p,quality=note_features(notes,basic,crepe);paths,similarity=recurring_paths(notes,f)
    evidence=[[] for _ in notes]
    for path in paths:
        pairs=path['pairs']
        for k,(a,b) in enumerate(pairs):
            nearby=pairs[max(0,k-6):min(len(pairs),k+7)]
            anchors=[]
            for x,y in nearby:
                if (x,y)==(a,b) or notes[x]['midi']%12!=notes[y]['midi']%12:continue
                delta=notes[x]['midi']-notes[y]['midi']
                anchors.append((delta,max(.1,min(quality[x],quality[y]))))
            if len(anchors)<5:continue
            choices=sorted({delta for delta,w in anchors})
            weights=[sum(w for d,w in anchors if d==delta) for delta in choices]
            offset=choices[int(np.argmax(weights))];support=max(weights)/sum(weights)
            if support<.72 or abs(offset)>24:continue
            if similarity[a,b]<.65:continue
            for target,donor,shift in [(a,b,offset),(b,a,-offset)]:
                evidence[target].append({'donor_index':donor,'midi':int(notes[donor]['midi']+shift),
                    'strength':float(quality[donor]*support*similarity[a,b]),
                    'anchor_agreement':support,'matched_notes':len(pairs),'offset':shift})
    out=[];audit=[]
    for i,n in enumerate(notes):
        old=n['midi'];votes={};sources={}
        for item in evidence[i]:
            # One donor cannot gain multiple votes from overlapping paths.
            key=(item['donor_index'],item['midi'])
            if key not in sources or item['strength']>sources[key]['strength']:sources[key]=item
        for item in sources.values():votes[item['midi']]=votes.get(item['midi'],0)+item['strength']
        new=old;reason='retain'
        if votes:
            candidate=max(votes,key=votes.get);supporters=[e for e in sources.values() if e['midi']==candidate]
            strength=votes[candidate];own=max(.22,float(quality[i]))+votes.get(old,0)
            acoustic=p[i,candidate-21] if 21<=candidate<=108 else 0.
            current=p[i,old-21] if 21<=old<=108 else 0.
            allowed=(abs(candidate-old) in (12,24) or abs(candidate-old)<=2)
            strong_motif=(len(supporters)>=2 or any(e['matched_notes']>=16 and e['strength']>.65 for e in supporters))
            if (candidate!=old and allowed and strong_motif and strength>own+.15
                and acoustic>.09 and acoustic>=current*.20):
                new=candidate;reason='repeated_motif_with_register_anchors_and_audio_support'
        out.append({**n,'midi':int(new)})
        audit.append({'start_ms':n['start_ms'],'old_midi':old,'new_midi':int(new),'reason':reason,
                      'own_quality':float(quality[i]),'votes':votes,'evidence':list(sources.values())})
    return out,{'policy':'same-recording-motif-v1','reference_used':False,'schedule_unchanged':True,
                'changes':sum(n['midi']!=q['midi'] for n,q in zip(notes,out)),'paths':paths,'notes':audit}
