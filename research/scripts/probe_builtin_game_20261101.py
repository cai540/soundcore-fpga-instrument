"""Source-only interval proposals from the phone decoder; no lyrics/reference in inference."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build/score_api_20261030/packages'));sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.signal import resample_poly
from soundcore_audio.game import GameModel
folder=ROOT/'build/vocal_oss_20261029/game_models/medium/GAME-1.0.3-medium-onnx'
out=ROOT/'build/builtin_recognition_20261101/game';out.mkdir(exist_ok=True)
model=GameModel(folder,out/'cache',threads=2)
for ident in ['zuguo','qiansixi','chilege']:
    pcm=np.fromfile(out.parent/(ident+'.f32'),dtype='<f4');wave=resample_poly(pcm,441,160).astype(np.float32)
    encoded=model.encode(wave)
    proposed=json.loads((out.parent/'audio'/(ident+'_notes.json')).read_text(encoding='utf8'))
    notes=proposed['notes'];cuts=sorted(set([0,encoded.frames]+[round(n[k]/10) for n in notes for k in ['start_ms']]+[round((n['start_ms']+n['duration_ms'])/10)for n in notes]))
    activation=model.estimate(encoded,np.array(cuts,dtype=int))
    for n in notes:
        i=cuts.index(round(n['start_ms']/10));row=activation[i,np.arange(128)*2]
        n['proposal_midi']=n['midi'];n['midi']=int(np.argmax(row[1:])+1)
    (out/(ident+'_notes.json')).write_text(json.dumps(proposed,indent=2),encoding='utf8')
    print(ident,len(notes),encoded.frames,flush=True)
