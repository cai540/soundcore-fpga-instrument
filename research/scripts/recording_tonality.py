"""Recording-derived soft pitch collection; never a supplied song key."""
import numpy as np

def infer_collection(acoustic_note_hints):
    histogram=np.zeros(12)
    for n in acoustic_note_hints:
        if n['duration_ms']<120 or not 24<=n['midi']<=108:continue
        histogram[n['midi']%12]+=min(n['duration_ms'],800)/1000
    total=float(histogram.sum())
    scale=np.array([0,2,4,5,7,9,11]);options=[]
    for root in range(12):
        mask=np.zeros(12,bool);mask[(scale+root)%12]=True
        options.append((float(histogram[mask].sum()/max(total,1e-9)),root,mask))
    options.sort(key=lambda q:q[0],reverse=True)
    best=options[0];margin=best[0]-options[1][0]
    plausible=[q for q in options if q[0]>=best[0]-.015]
    union=np.any(np.array([q[2] for q in plausible]),axis=0)
    enabled=total>=4 and best[0]>=.85 and int(union.sum())<=10
    return {'enabled':bool(enabled),'pitch_classes':np.flatnonzero(union).tolist(),
            'coverage':best[0],'runner_up_margin':margin,'histogram':histogram.tolist(),
            'plausible_collections':len(plausible),
            'source':'acoustic_note_model_on_this_recording','provided_key_or_score':False}
