"""Conservative lyric-free reattack validation using AUDIO-derived ASR times.

Text content is deliberately ignored. Timing is a fallible supporting cue;
bad/overlapping/very long token alignments cannot dictate the note schedule.
Never equal-divide a whole sentence into supposedly real syllable onsets.
"""
import numpy as np
from vocal_event_refinement import refine_events

def acoustic_character_attacks(alignment,notes,evidence,acoustic):
    word=evidence['word'];rms=acoustic['rms'];attacks=[];rejected=[]
    model_starts=np.array([n['start_ms'] for n in notes])
    floor=max(float(np.quantile(rms,.9))*.035,1e-5)
    previous=-1
    for c in alignment.get('characters',[]):
        a=c['start_ms'];z=c['end_ms'];reason=None
        if c.get('estimated_split'):reason='multi_character_token_time_is_estimated'
        elif not 70<=z-a<=3500:reason='implausible_token_duration'
        elif a<previous:reason='non_monotonic_alignment'
        previous=max(previous,a)
        k=max(0,min(len(word)-1,a//10));lo=max(0,k-15);hi=min(len(word),k+16)
        nearest=int(model_starts[np.argmin(abs(model_starts-a))]) if len(model_starts) else a
        if reason is None and not np.mean(rms[max(0,a//10):min(len(rms),(z+9)//10)]>floor)>.5:
            reason='little_acoustic_voice_energy'
        if reason is None:
            j=lo+int(word[lo:hi].argmax());t=j*10
            if word[j]>=.45:
                attacks.append(t)
            elif abs(nearest-a)<=180:
                attacks.append(nearest)
            else:reason='no_acoustic_or_transcription_attack_near_token'
        if reason:rejected.append({'start_ms':a,'end_ms':z,'reason':reason})
    return sorted(set(attacks)),rejected

def refine_phonetic_events(notes,alignment,evidence,pesto,acoustic):
    attacks,rejected=acoustic_character_attacks(alignment,notes,evidence,acoustic)
    # Only acoustically corroborated ASR boundaries protect reattacks.
    result,audit=refine_events(notes,evidence,pesto,acoustic,attacks)
    audit.update(policy='acoustically-checked-asr-reattacks-v1',
                 protected_attacks_ms=attacks,rejected_asr_times=rejected,
                 asr_text_used_for_pitch_or_note_count=False,
                 supplied_lyrics_or_reference_used=False)
    return result,audit
