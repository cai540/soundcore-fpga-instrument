"""Export immutable phone assets. No API credentials, recordings or song answers."""
from pathlib import Path
import hashlib,json,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build/score_api_20261030/packages'))
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import torch,torchcrepe,onnxruntime as ort
    torch.set_num_threads(4);torch.manual_seed(0)
    assets=ROOT/'app/android/app/src/main/assets';audio=assets/'models';audio.mkdir(exist_ok=True)
    out=ROOT/'build/builtin_recognition_20261101';out.mkdir(exist_ok=True)
    checkpoint=Path(torchcrepe.__file__).parent/'assets/tiny.pth'
    model=torchcrepe.model.Crepe('tiny').eval()
    model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True),strict=True)
    target=audio/'crepe_tiny.onnx'
    torch.onnx.export(model,torch.randn(2,1024),str(target),opset_version=17,dynamo=False,
        input_names=['frames'],output_names=['salience'],dynamic_axes={'frames':{0:'N'},'salience':{0:'N'}})
    options=ort.SessionOptions();options.intra_op_num_threads=4
    session=ort.InferenceSession(str(target),options,providers=['CPUExecutionProvider'])
    parity=[]
    with torch.inference_mode():
        for n in (1,7,32):
            x=torch.randn(n,1024);expected=model(x).numpy();actual=session.run(None,{'frames':x.numpy()})[0]
            error=float(abs(expected-actual).max());assert error<1e-4
            parity.append({'batch':n,'max_absolute_error':error})
    meta={'model':'CREPE-tiny','source':'https://github.com/maxrmorrison/torchcrepe',
        'license':'MIT','weights':'Original released pretrained weights, no project retraining',
        'sample_rate':16000,'window':1024,'hop':320,'acoustic_hop':160,'bins':360,'cents_origin':1997.3794084376191,
        'cents_step':20,'checkpoint_sha256':sha(checkpoint),'onnx_sha256':sha(target),'onnx_bytes':target.stat().st_size,
        'frontend':'zero pad 512 each side; subtract window mean; divide sample standard deviation ddof1 floored at1e-10',
        'parity':parity,'third_party_api_required':False,'runtime_model_download':False}
    (audio/'crepe_tiny.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    folder=ROOT/'build/fpga_omr_20261031/model'
    with np.load(folder/'integer_weights.npz',allow_pickle=False)as weights:
        symbol={k:weights[k].tolist() for k in weights.files}
    symbol.update(model='binary-mlp-256-64-11-v1',model_crc32=3866258960,inference_location='phone')
    (assets/'offline/symbol_model.json').write_text(json.dumps(symbol,separators=(',',':')),encoding='utf8')
    vectors=np.load(folder/'validation_vectors.npz',allow_pickle=False)
    (out/'symbol_vectors_keys.json').write_text(json.dumps({k:list(vectors[k].shape) for k in vectors.files}),encoding='utf8')
    licenses=assets/'open_source_licenses'
    for name,url in [('TORCHCREPE_LICENSE.txt','https://raw.githubusercontent.com/maxrmorrison/torchcrepe/master/LICENSE'),
                     ('CREPE_LICENSE.txt','https://raw.githubusercontent.com/marl/crepe/master/LICENSE')]:
        with urllib.request.urlopen(url,timeout=30)as response:(licenses/name).write_bytes(response.read())
    (out/'asset_export.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
