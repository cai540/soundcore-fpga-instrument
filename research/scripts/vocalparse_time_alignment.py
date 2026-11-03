"""Align audio-inferred character/main-note units to the original waveform.

VocalParse supplies symbolic note values, not timestamps. This duration-aware
dynamic program uses acoustic pitch class, voicing, and word-boundary evidence
for timing. The input score must come from audio inference, not a song library.
"""
import numpy as np
from grounded_pitch_decoder import hz_to_midi

BEATS={'<NOTE_32>':.125,'<NOTE_DOT_32>':.1875,'<NOTE_16>':.25,'<NOTE_DOT_16>':.375,
       '<NOTE_8>':.5,'<NOTE_DOT_8>':.75,'<NOTE_4>':1.,'<NOTE_DOT_4>':1.5,
       '<NOTE_2>':2.,'<NOTE_DOT_2>':3.,'<NOTE_1>':4.,'<NOTE_DOT_1>':6.}

def main_units(parsed):
    units=[]
    for word,pitch,note in zip(parsed['words'],parsed['pitches'],parsed['notes']):
        beat=BEATS.get(note,1.)
        if word in ['AP','SP'] or pitch==0:continue
        if word=='·' and units:
            units[-1]['components'].append((int(pitch),beat));units[-1]['beats']+=beat
        else:units.append({'word':word,'beats':beat,'components':[(int(pitch),beat)]})
    for u in units:
        mass={}
        for p,b in u['components']:mass[p]=mass.get(p,0)+b
        u['midi']=max(mass,key=mass.get)
    return units

def align_units(pcm,parsed,evidence,pesto,units_override=None):
    units=main_units(parsed) if units_override is None else units_override
    if not units:return [],{'accepted':False,'reason':'no_parseable_voiced_units'}
    T=(len(pcm)+319)//320
    if len(units)*3>T:return [],{'accepted':False,'reason':'impossible_note_count'}
    pad=np.pad(np.asarray(pcm,float),(160,480))
    frames=np.lib.stride_tricks.sliding_window_view(pad,320)[::320][:T]
    rms=np.sqrt(np.mean(frames**2,axis=1));level=max(float(np.quantile(rms,.9)),1e-6)
    energy=np.clip((rms/level-.025)/.1,0,1)
    def grid(raw):
        raw=np.asarray(raw);idx=np.minimum(np.arange(T)*2,len(raw)-1);return raw[idx]
    rp=grid(hz_to_midi(evidence['rmvpe']));pp=grid(pesto['midi']);pc=grid(pesto['confidence'])
    word=grid(evidence['word'])
    voiced=energy*np.maximum((rp>24).astype(float),((pp>24)&(pc>.5)).astype(float))
    rest_cost=voiced*1.7;rest_prefix=np.r_[0,np.cumsum(rest_cost)]
    bpm=parsed.get('bpm',120);bpm=bpm if 30<=bpm<=240 else 120
    means=np.array([u['beats']*3000/bpm for u in units])
    ratio=max(float(np.sum(voiced>.3)),len(units)*4)/max(means.sum(),1.)
    means*=np.clip(ratio,.5,2.)
    previous=np.full(T+1,np.inf);previous[0]=0
    durations=np.zeros((len(units),T+1),np.int16)
    rests=np.zeros((len(units),T+1),np.int16)
    emission_rows=[]
    for i,(unit,mean) in enumerate(zip(units,means)):
        pitch=unit['midi'];track_cost=[]
        for raw,valid in [(rp,rp>24),(pp,(pp>24)&(pc>.5))]:
            distance=abs(raw-pitch)
            # Period ambiguity can affect F0 without changing the intended
            # word pitch. This folding is for alignment, never pitch editing.
            for shift in [-24,-12,12,24]:distance=np.minimum(distance,abs(raw+shift-pitch)+.15)
            track_cost.append(np.where(valid,np.minimum(distance,4.),np.nan))
        stack=np.array(track_cost);counts=np.sum(np.isfinite(stack),axis=0)
        fit=np.nansum(stack,axis=0)/np.maximum(counts,1)
        fit[counts==0]=1.
        frame_cost=.9*(1-voiced)+.16*np.minimum(fit,4.)*voiced
        emission_rows.append((frame_cost,fit))
        prefix=np.r_[0,np.cumsum(frame_cost)]
        # Optional source-measured rests before each word, including leading
        # silence. They are neither deleted nor replaced by a fixed pause.
        values=previous-rest_prefix
        minima=np.minimum.accumulate(values)
        is_new=np.r_[True,values[1:]<minima[:-1]]
        indexes=np.maximum.accumulate(np.where(is_new,np.arange(T+1),0))
        starts=minima+rest_prefix-.65*float(unit.get('onset_weight',1.))*np.r_[word,word[-1]]
        rests[i]=indexes
        best=np.full(T+1,np.inf)
        max_duration=min(T,max(120,int(mean*3.5)))
        for d in range(3,max_duration+1):
            cost=starts[:T+1-d]+prefix[d:]-prefix[:T+1-d]
            cost=cost+1.2*(np.log(d/max(mean,1.))/.7)**2
            better=cost<best[d:]
            best[d:][better]=cost[better];durations[i,d:][better]=d
        previous=best
    finish=int(np.argmin(previous+rest_prefix[-1]-rest_prefix))
    if not np.isfinite(previous[finish]):return [],{'accepted':False,'reason':'alignment_failed'}
    notes=[];audit=[];end=finish
    for i in range(len(units)-1,-1,-1):
        d=int(durations[i,end]);start=end-d
        if d<=0:return [],{'accepted':False,'reason':'invalid_backtrace'}
        u=units[i];a=start*20;z=min(len(pcm)//16,end*20)
        if z<=a:return [],{'accepted':False,'reason':'zero_duration'}
        notes.append({'start_ms':a,'duration_ms':z-a,'midi':u['midi'],'confidence':0.})
        fit=emission_rows[i][1][start:end]
        audit.append({'word':u['word'],'midi':u['midi'],'start_ms':a,'duration_ms':z-a,
                      'components':u['components'],'voiced_fraction':float(np.mean(voiced[start:end])),
                      'pitch_class_support_fraction':float(np.mean(fit<1.5))})
        end=int(rests[i,start])
    notes.reverse();audit.reverse()
    total_voice=sum(n['duration_ms']*q['voiced_fraction'] for n,q in zip(notes,audit))/max(sum(n['duration_ms'] for n in notes),1)
    support=sum(n['duration_ms']*q['pitch_class_support_fraction'] for n,q in zip(notes,audit))/max(sum(n['duration_ms'] for n in notes),1)
    return notes,{'accepted':bool(total_voice>.45 and support>.45),'reason':'acoustic_support_check',
                  'units':audit,'mean_voiced_fraction':total_voice,'pitch_class_support_fraction':support,
                  'bpm':bpm,'duration_prior_scale':float(np.clip(ratio,.5,2.)),
                  'timing_grid_ms':20,'pitch_source':'audio_only_vocalparse','reference_used':False}
