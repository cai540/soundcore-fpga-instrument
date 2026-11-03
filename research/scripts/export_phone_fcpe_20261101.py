"""Evaluate the official bundled FCPE model as a phone-sized singing observer."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
for folder in ['build/score_api_20261030/packages','build/fcpe_20261030/packages']:sys.path.insert(0,str(ROOT/folder))
import numpy as np
import torch
from torchfcpe import spawn_bundled_infer_model
import onnxruntime as ort
torch.set_num_threads(4)
out=ROOT/'build/builtin_recognition_20261101/fcpe';out.mkdir(exist_ok=True)
infer=spawn_bundled_infer_model(device='cpu').eval();model=infer.model.eval()
print(json.dumps(infer.args_dict,indent=2),flush=True)
print('FRONTEND',infer.wav2mel,flush=True)
x=torch.randn(1,256,128)
torch.onnx.export(model,x,str(out/'fcpe.onnx'),opset_version=17,dynamo=False,input_names=['mel'],output_names=['salience'],
    dynamic_axes={'mel':{1:'T'},'salience':{1:'T'}})
options=ort.SessionOptions();options.intra_op_num_threads=2
session=ort.InferenceSession(str(out/'fcpe.onnx'),options,providers=['CPUExecutionProvider'])
parity=[]
with torch.inference_mode():
 for count in [128,256,512]:
  x=torch.randn(1,count,128);a=model(x).numpy();b=session.run(None,{'mel':x.numpy()})[0]
  error=float(abs(a-b).max());assert error<1e-4;parity.append({'frames':count,'max_error':error})
print(parity,flush=True)
for ident in ['zuguo','qiansixi','chilege']:
 pcm=np.fromfile(out.parent/(ident+'.f32'),dtype='<f4')
 with torch.inference_mode():
  mel=infer.wav2mel(torch.from_numpy(pcm)[None,:,None],16000)
  latent=model(mel).numpy()[0]
 np.save(out/(ident+'_salience.npy'),latent)
 print(ident,mel.shape,latent.shape,float(np.median(latent.max(axis=1))),flush=True)
torch.save(model.state_dict(),out/'model_state_audit.pt')
(out/'export.json').write_text(json.dumps({'config':infer.args_dict,'parity':parity,'sha256':hashlib.sha256((out/'fcpe.onnx').read_bytes()).hexdigest()},indent=2),encoding='utf8')
