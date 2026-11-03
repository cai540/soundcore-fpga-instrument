"""Inspect native Whisper alignment tokens, without a known transcript."""
from pathlib import Path
import json,torch,numpy as np
from local_lyric_alignment import LyricAlignmentEngine,B
from transcribe_vocal_oss import decode_audio
e=LyricAlignmentEngine()
x=decode_audio(Path('songs/source/wodezuguo_vocals_20261026.mp3'))[47090*16:63090*16]
features=e.processor(x,sampling_rate=16000,return_tensors='pt',return_attention_mask=True)
features={k:v.to(e.device,dtype=e.dtype if v.is_floating_point() else v.dtype) for k,v in features.items()}
with torch.inference_mode():
    r=e.model.generate(**features,language='zh',task='transcribe',num_beams=3,
        return_timestamps=True,return_token_timestamps=True,return_dict_in_generate=True,
        max_new_tokens=256,num_frames=len(x)//160)
rows=[]
for token,t in zip(r['sequences'][0].tolist(),r['token_timestamps'][0].tolist()):
    rows.append({'token':token,'text':e.processor.tokenizer.decode([token]),'time':t})
(B/'token_smoke.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(rows,ensure_ascii=False))
