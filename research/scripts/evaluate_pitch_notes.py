"""Event-based diagnostic; pitch-blind chronological one-to-one matching.

Editorial references are not independent gold labels. This evaluator does
not supply any notes, lyrics, or offsets to the inference engine.
"""
from pathlib import Path
import argparse,csv,json
import numpy as np

def align_intervals(reference,predicted):
    N=len(reference);M=len(predicted);dp=np.zeros((N+1,M+1));back=np.zeros((N+1,M+1),np.int8)
    back[1:,0]=1;back[0,1:]=2
    for i,r in enumerate(reference,1):
        a=r['start_ms'];z=a+r['duration_ms']
        for j,n in enumerate(predicted,1):
            b=n['start_ms'];y=b+n['duration_ms'];overlap=max(0,min(z,y)-max(a,b))
            reward=overlap/max(z-a,y-b,1)
            # Match score uses time overlap only, never pitch identity.
            reward=reward if overlap>=min(80,.25*min(z-a,y-b)) else -1e6
            choices=[dp[i-1,j-1]+reward,dp[i-1,j],dp[i,j-1]]
            k=int(np.argmax(choices));dp[i,j]=choices[k];back[i,j]=k
    pairs=[];i=N;j=M
    while i or j:
        k=int(back[i,j])
        if k==0:pairs.append((i-1,j-1));i-=1;j-=1
        elif k==1:i-=1
        else:j-=1
    return pairs[::-1]

def evaluate(reference,predicted):
    pairs=align_intervals(reference,predicted);correct=chroma=octave=semitone=0;errors=[]
    for i,j in pairs:
        r=reference[i];n=predicted[j];delta=n['midi']-r['midi']
        correct+=delta==0;chroma+=delta%12==0;octave+=abs(delta) in (12,24);semitone+=abs(delta)==1
        if delta:errors.append({'reference_index':i,'predicted_index':j,'source_ms':r['start_ms'],
                              'reference_midi':r['midi'],'predicted_midi':n['midi'],'delta_semitones':delta})
    if reference:
        first=min(q['start_ms'] for q in reference);last=max(q['start_ms']+q['duration_ms'] for q in reference)
        covered=[q for q in predicted if q['start_ms']<last and q['start_ms']+q['duration_ms']>first]
    else:first=last=0;covered=[]
    return {'reference_voiced_notes':len(reference),'predicted_notes':len(predicted),'matched_by_time':len(pairs),
            'correct_pitch_and_octave_notes':int(correct),'correct_pitch_class_notes':int(chroma),
            'exact_recall_including_missed_notes':correct/max(len(reference),1),
            'exact_precision_including_extra_notes':correct/max(len(predicted),1),
            'octave_error_notes':int(octave),'one_semitone_error_notes':int(semitone),
            'missed_notes':len(reference)-len(pairs),'extra_notes':len(predicted)-len(pairs),
            'reference_outer_span_ms':[first,last],'predictions_in_outer_reference_span':len(covered),
            'predictions_outside_reference_span_unscored':len(predicted)-len(covered),
            'exact_precision_in_outer_reference_span':correct/max(len(covered),1),
            'extra_notes_inside_outer_reference_span':len(covered)-len(pairs),
            'outer_span_does_not_imply_every_interval_has_a_gold_label':True,
            'errors':errors,'reference_kind':'prior_editorial_proxy_not_independent_gold',
            'real_world_90_percent_verified':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--notes',type=Path,required=True);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    pred=[{'start_ms':int(q['start_ms']),'duration_ms':int(q['duration_ms']),'midi':int(q['midi'])}
          for q in csv.DictReader(args.notes.open(encoding='utf8'))]
    rows=list(csv.DictReader(args.reference.open(encoding='utf8')))
    ref=[{'start_ms':round(float(q['source_start_s'])*1000),'duration_ms':round((float(q['source_end_s'])-float(q['source_start_s']))*1000),
          'midi':int(q['source_midi'])} for q in rows if int(q['source_midi'])>0]
    result=evaluate(ref,pred);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='errors'},ensure_ascii=False))

if __name__=='__main__':main()
