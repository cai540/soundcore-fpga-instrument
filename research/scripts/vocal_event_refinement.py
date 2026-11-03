"""Vowel-center pitch and phonetic reattack validation on model note events.

Starts come from a full transcription model, not instantaneous F0 crossings.
The optional ASR start list is itself audio-derived. No reference score enters.
"""
import numpy as np
from vocal_pitch_center import estimate_center
from recording_tonality import infer_collection


def refine_events(notes,evidence,pesto,acoustic,asr_starts=None,merge_same_vowel=True):
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    pp=pesto['midi'];pc=pesto['confidence'];out=[];audits=[]
    tonal=infer_collection(notes);allowed=set(tonal['pitch_classes']) if tonal['enabled'] else None
    for n in notes:
        a=(n['start_ms']+9)//10;z=min(len(pp),(n['start_ms']+n['duration_ms']+9)//10)
        trim=min(5,max(0,(z-a)//8));s=a+trim;e=z-min(trim,3);old=n['midi'];centers=[];stable=[]
        for track,valid in [(rm,np.isfinite(rm)),(pp,pc>.6)]:
            value=track[s:e];ok=valid[s:e]&(value>24)
            if np.sum(ok)<max(8,(e-s)*.45):continue
            value=old+(value[ok]-old+6)%12-6;time=np.arange(s,e)[ok]*.01
            keep=abs(value-old)<2.4;value=value[keep];time=time[keep]
            if len(value)<8:continue
            fit=estimate_center(time,value)
            if fit.get('vibrato'):center=fit['center'];clear=True
            else:
                low,high=np.quantile(value,[.1,.9]);v=value[(value>=low)&(value<=high)]
                center=float(np.mean(v));clear=float(np.quantile(value,.8)-np.quantile(value,.2))<.75
            centers.append(center);stable.append(bool(clear))
        new=old
        if len(centers)==2 and max(centers)-min(centers)<.4 and all(stable):
            center=float(np.mean(centers));target=int(np.floor(center+.5))
            if abs(target-old)==1 and abs(center-old)>.62:
                # Weak collection prior cannot suppress a clearly stable
                # chromatic note; ambiguous vibrato is kept in its context.
                if allowed is None or target%12 in allowed or (abs(center-target)<.2 and n['duration_ms']>=400):new=target
        out.append({**n,'midi':new});audits.append({'start_ms':n['start_ms'],'old_midi':old,'new_midi':new,'centers':centers,'stable':stable})
    merged=[];merges=[];word=evidence['word'];rms=acoustic['rms']
    for n in out:
        if merge_same_vowel and merged and merged[-1]['midi']==n['midi'] and merged[-1]['start_ms']+merged[-1]['duration_ms']==n['start_ms']:
            k=n['start_ms']//10
            if 15<=k<len(rms)-16:
                peak=float(np.max(word[k-6:k+7]));left=float(np.quantile(rms[k-15:k-3],.8));right=float(np.quantile(rms[k+3:k+15],.8))
                valley=float(np.min(rms[k-3:k+4]))/max(min(left,right),1e-8)
                asr_attack=asr_starts is not None and any(abs(n['start_ms']-t)<100 for t in asr_starts)
                if peak<.35 and valley>.72 and not asr_attack:
                    merged[-1]['duration_ms']+=n['duration_ms'];merges.append({'start_ms':n['start_ms'],'midi':n['midi'],'word_boundary_peak':peak,'rms_valley_ratio':valley});continue
        merged.append(dict(n))
    return merged,{'policy':'vowel-center-and-phonetic-attacks-v1','pitch_edits':audits,'same_vowel_merges':merges,
                   'same_vowel_merge_enabled':merge_same_vowel,
                   'asr_protection_used':asr_starts is not None,'pitch_changes':sum(n['old_midi']!=n['new_midi'] for n in audits),
                   'new_pitch_boundaries_invented':False,'reference_or_known_lyrics_used':False,'recording_tonality':tonal}
