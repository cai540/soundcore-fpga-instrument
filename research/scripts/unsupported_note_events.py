"""Remove only acoustically unsupported events, not all short notes.

A real short note has stable pitch or a trained onset/phonetic attack and is
retained. A brief A-B-A fluctuation needs corroborated vowel vibrato and weak
boundaries before it can be absorbed into A. Existing reattacks stay separate.
"""
import numpy as np
from note_probability_fusion import basic_times
from vocal_pitch_center import estimate_center


def cleanup(notes,evidence,pesto,basic,acoustic):
    if not notes:return [],{'deleted':[],'absorbed':[],'reference_used':False}
    bt=basic_times(len(basic['note']));bp=np.asarray(basic['note'],float)
    rm=np.where(evidence['rmvpe']>0,69+12*np.log2(np.maximum(evidence['rmvpe'],1)/440),np.nan)
    pp=pesto['midi'];pc=pesto['confidence'];word=evidence['word'];flux=acoustic['flux'];rms=acoustic['rms']
    out=[];deleted=[];absorbed=[]
    for i,n in enumerate(notes):
        s=n['start_ms'];e=s+n['duration_ms'];a=(s+9)//10;z=min(len(pp),(e+9)//10)
        x,y=np.searchsorted(bt,[s/1000,e/1000]);b=bp[x:y].mean(axis=0) if y>x else np.zeros(88)
        contrast=float(b.max()-np.median(b))
        r=rm[a:z];p=pp[a:z];conf=pc[a:z]
        if (n['duration_ms']<=400 and contrast<.045 and np.mean(np.isfinite(r))<.2 and np.mean(conf>.5)<.2):
            deleted.append({**n,'reason':'no_voiced_or_trained_note_activity'});continue
        if (out and i+1<len(notes) and n['duration_ms']<=200
            and out[-1]['midi']==notes[i+1]['midi'] and 0<abs(n['midi']-out[-1]['midi'])<=2
            and s==out[-1]['start_ms']+out[-1]['duration_ms']
            and notes[i+1]['start_ms']==e):
            left=out[-1];right=notes[i+1];target=left['midi']
            attack=max(float(word[max(0,a-2):a+3].max()),0.)
            phonetic=float(flux[max(0,a-2):a+3].max())
            u=max(left['start_ms']//10,a-65);v=min(len(pp),(right['start_ms']+right['duration_ms'])//10,z+65)
            fits=[]
            for track,mask in [(rm,np.isfinite(rm)),(pp,pc>.5)]:
                value=track[u:v];valid=mask[u:v]
                folded=target+(value-target+6)%12-6
                fit=estimate_center(np.arange(u,v)[valid]*.01,folded[valid]);fits.append(fit)
            supported=all(q.get('vibrato') and abs(q['center']-target)<.45 for q in fits)
            stable=np.mean(abs(target+(p-target+6)%12-6-n['midi'])<.35) if len(p) else 0.
            if supported and attack<.9 and phonetic<.15 and stable<.45:
                out[-1]['duration_ms']+=n['duration_ms'];absorbed.append({**n,'reason':'vibrato_island_without_phonetic_attack'});continue
        out.append(dict(n))
    return out,{'policy':'unsupported-events-v1','deleted':deleted,'absorbed':absorbed,'reference_used':False}
