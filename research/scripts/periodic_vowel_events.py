"""Remove note events only when two observations explain them as ONE vibrato.

Real stepped plateaus, rests, phonetic reattacks and unsupported fits survive.
This does not impose a per-syllable note budget or use supplied lyric text.
"""
import numpy as np
from vocal_pitch_center import estimate_center

def collapse_periodic_vowels(notes,evidence,pesto,minimum_fragments=3):
    if minimum_fragments not in (2,3):raise ValueError('Two or three fragments required')
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    pp=np.asarray(pesto['midi']);pc=np.asarray(pesto['confidence']);word=evidence['word']
    result=[];audits=[];i=0
    while i<len(notes):
        accepted=None
        for j in range(i+1,min(len(notes),i+10)):
            a=notes[i]['start_ms'];z=notes[j]['start_ms']+notes[j]['duration_ms']
            if z-a>2200:break
            left=notes[j-1];right=notes[j]
            if left['start_ms']+left['duration_ms']!=right['start_ms']:break
            k=right['start_ms']//10
            attack=float(np.max(word[max(0,k-4):min(len(word),k+5)]))
            if attack>.45:break
            pitches=[n['midi'] for n in notes[i:j+1]]
            if max(pitches)-min(pitches)>4:break
            if j-i+1<minimum_fragments or z-a<(300 if minimum_fragments==2 else 400) or len(set(pitches))<2:continue
            anchor=notes[i]['midi'];s=(a+29)//10;e=min(len(pp),(z-20+9)//10);fits=[]
            for v,valid in [(rm,np.isfinite(rm)),(pp,pc>.6)]:
                x=v[s:e];ok=valid[s:e]&(x>24)
                if ok.mean()<.65:break
                folded=anchor+(x[ok]-anchor+6)%12-6
                fit=estimate_center(np.arange(s,e)[ok]*.01,folded)
                if not fit.get('vibrato') or fit['explained']<.70:break
                fits.append(fit)
            if len(fits)!=2:continue
            if abs(fits[0]['center']-fits[1]['center'])>.35 or abs(fits[0]['frequency_hz']-fits[1]['frequency_hz'])>1.0:continue
            center=float(np.mean([f['center'] for f in fits]));choices=sorted(set(pitches))
            target=min(choices,key=lambda p:abs(p-center))
            if abs(target-center)>.6:continue
            accepted=(j,target,fits)
        if accepted:
            j,target,fits=accepted;end=notes[j]['start_ms']+notes[j]['duration_ms']
            result.append({**notes[i],'duration_ms':end-notes[i]['start_ms'],'midi':target})
            audits.append({'start_ms':notes[i]['start_ms'],'end_ms':end,'before_pitches':[n['midi'] for n in notes[i:j+1]],
                           'after_midi':target,'vowel_fits':fits})
            i=j+1
        else:result.append(dict(notes[i]));i+=1
    return result,{'policy':'two-track-periodic-vowel-events-v1','collapsed_regions':audits,
                   'minimum_fragments':minimum_fragments,
                   'events_removed':len(notes)-len(result),'rests_filled':0,'reference_or_lyrics_used':False}
