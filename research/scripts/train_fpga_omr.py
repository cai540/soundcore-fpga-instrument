"""Train a small original model. OrpheusNet inspired the segmented architecture,
not these weights/code. All real score pages remain outside the training set."""
from pathlib import Path
import argparse,hashlib,inspect,json,math,random,sys,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import torch
from torch import nn
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fpga_omr.model import normalize,integer_forward,classify,pack_pixels,HIDDEN,CLASSES

TRAIN=['arial.ttf','arialbd.ttf','ariali.ttf','times.ttf','timesbd.ttf','timesi.ttf','calibri.ttf','calibrib.ttf','cambria.ttc','msyh.ttc','simsun.ttc','simhei.ttf','consola.ttf','consolab.ttf','georgia.ttf','georgiab.ttf','trebuc.ttf','trebucbd.ttf','bookos.ttf','bookosb.ttf']
VALID=['verdana.ttf','verdanab.ttf','tahoma.ttf','tahomabd.ttf','pala.ttf','palab.ttf','corbel.ttf','corbelb.ttf']
NEGATIVE=list(',.()[]{}-+xyzACEFGH')

def dataset(fonts,count,seed):
    rng=random.Random(seed);x=np.zeros((count,256),dtype=np.uint8);y=np.zeros(count,dtype=np.int64)
    cache={}
    for i in range(count):
        label=i%CLASSES;size=rng.randint(15,36);path=rng.choice(fonts)
        key=(str(path),size)
        if key not in cache:cache[key]=ImageFont.truetype(str(path),size)
        font=cache[key]
        text=str(label) if label<10 else rng.choice(NEGATIVE)
        im=Image.new('L',(72,72),255);draw=ImageDraw.Draw(im)
        draw.text((12,4),text,font=font,fill=rng.randint(0,65),stroke_width=0)
        im=im.rotate(rng.uniform(-3,3),resample=Image.Resampling.BILINEAR,fillcolor=255)
        if rng.random()<.25:im=im.filter(ImageFilter.GaussianBlur(rng.uniform(.1,.45)))
        a=normalize(im).reshape(16,16)
        if rng.random()<.35:
            a=np.roll(a,(rng.choice([-1,0,1]),rng.choice([-1,0,1])),axis=(0,1))
        if rng.random()<.12:
            a=a.copy();a[rng.randrange(16),rng.randrange(16)]=rng.randrange(2)
        x[i]=a.reshape(-1);y[i]=label
    return x,y

def real_reference():
    folder=ROOT/'build/sheet_acceptance_20261031'
    manual=json.loads((folder/'manual_first_rows.json').read_text(encoding='utf8'))
    extras=json.loads((ROOT/'fpga_omr/manual_non_notes.json').read_text(encoding='utf8'))['non_notes']
    features=[];labels=[];identities=[]
    for name,ref in manual['samples'].items():
        row=json.loads((folder/'pixel_runs'/f'{name}_row_1.json').read_text(encoding='utf8'))
        glyphs=row['line']['glyphs'];cursor=0
        im=Image.open(folder/'inputs'/f'{name}.jpg')
        for g in glyphs:
            box=(g['x'],g['y'],g['x']+g['w'],g['y']+g['h'])
            extra=next((e for e in extras if e['page']==name and e['box']==list(box)),None)
            if extra:label=extra['class']
            else:label=ref['degree'][cursor];cursor+=1
            features.append(normalize(im.crop(box)));labels.append(label)
            identities.append({'page':name,'box':list(box),'label':label})
        assert cursor==len(ref['degree'])
    return np.asarray(features),np.asarray(labels),identities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--epochs',type=int,default=45);ap.add_argument('--count',type=int,default=24200);ap.add_argument('--out',type=Path,default=ROOT/'build/fpga_omr_20261031/model');args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True);start=time.monotonic();torch.set_num_threads(4)
    random.seed(314159);np.random.seed(314159);torch.manual_seed(314159)
    fonts=Path('C:/Windows/Fonts');train=[fonts/f for f in TRAIN if(fonts/f).exists()];valid=[fonts/f for f in VALID if(fonts/f).exists()]
    assert train and valid and not(set(train)&set(valid))
    families=lambda paths:{ImageFont.truetype(str(p),20).getname()[0] for p in paths}
    assert not(families(train)&families(valid)),'Font-family leakage'
    print('Generating synthetic font-separated data',flush=True)
    identity=hashlib.sha256((inspect.getsource(dataset)+inspect.getsource(normalize)+str(args.count)+str(train)+str(valid)).encode()).hexdigest()
    cache=out/('synthetic_'+identity[:16]+'.npz')
    if cache.exists():
        with np.load(cache)as d:x,y,vx,vy=(d[k]for k in ['x','y','vx','vy'])
    else:
        x,y=dataset(train,args.count,314159);vx,vy=dataset(valid,3300,271828);np.savez_compressed(cache,x=x,y=y,vx=vx,vy=vy)
    rx,ry,identities=real_reference()
    device='cuda' if torch.cuda.is_available() else'cpu'
    model=nn.Sequential(nn.Linear(256,HIDDEN),nn.ReLU(),nn.Linear(HIDDEN,CLASSES)).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=.0001)
    xt=torch.tensor(x,dtype=torch.float32,device=device);yt=torch.tensor(y,device=device)
    vt=torch.tensor(vx,dtype=torch.float32,device=device);rt=torch.tensor(rx,dtype=torch.float32,device=device)
    best=-1;best_state=None
    for epoch in range(args.epochs):
        model.train();perm=torch.randperm(len(x),device=device)
        for idx in perm.split(512):
            opt.zero_grad(set_to_none=True);loss=nn.functional.cross_entropy(model(xt[idx]),yt[idx]);loss.backward();opt.step()
        model.eval()
        with torch.no_grad():acc=float((model(vt).argmax(1).cpu().numpy()==vy).mean())
        if acc>best:best=acc;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        if (epoch+1)%10==0:print(f'epoch {epoch+1}, held-out fonts {acc:.4f}',flush=True)
    model.load_state_dict(best_state);model.eval()
    torch.save(best_state,out/'float_weights.pt')
    w1=model[0].weight.detach().cpu().numpy();b1=model[0].bias.detach().cpu().numpy();w2=model[2].weight.detach().cpu().numpy();b2=model[2].bias.detach().cpu().numpy()
    q1=math.floor(math.log2(127/np.max(np.abs(w1))));q2=math.floor(math.log2(127/np.max(np.abs(w2))))
    with torch.no_grad():calibration=model[1](model[0](xt[:4096])).cpu().numpy()
    shift=max(0,math.ceil(math.log2(max(1,float(calibration.max())*2**q1)/220)))
    step=2.0**(shift-q1)
    weights=dict(w1=np.rint(w1*2**q1).clip(-127,127).astype(np.int8),b1=np.rint(b1*2**q1).astype(np.int32),w2=np.rint(w2*2**q2).clip(-127,127).astype(np.int8),b2=np.rint(b2*2**q2/step).astype(np.int32),shift1=np.array(shift,dtype=np.int32))
    np.savez(out/'integer_weights.npz',**weights)
    metrics={}
    for name,features,labels in [('held_out_fonts',vx,vy),('real_manual_first_rows',rx,ry)]:
        with torch.no_grad():float_predictions=model(torch.tensor(features,dtype=torch.float32,device=device)).argmax(1).cpu().numpy()
        logits=integer_forward(features,weights);predictions,margin=classify(logits)
        metrics[name]={'count':len(labels),'float_correct':int((float_predictions==labels).sum()),'integer_correct':int((predictions==labels).sum()),'integer_accuracy':float((predictions==labels).mean()),'quantized_predictions_changed':int((predictions!=float_predictions).sum()),'confusion':np.array([[int(((labels==a)&(predictions==b)).sum())for b in range(CLASSES)]for a in range(CLASSES)]).tolist()}
        if name.startswith('real'):
            metrics[name]['errors']=[{**identities[i],'predicted':int(predictions[i]),'margin':int(margin[i])}for i in range(len(labels))if predictions[i]!=labels[i]]
    for key in ('w1','w2','b1','b2'):
        a=weights[key].reshape(-1);bits=8 if key.startswith('w') else 32
        (out/(key+'.hex')).write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n'for v in a),encoding='ascii')
    test_x=np.concatenate([rx,vx[:77],np.zeros((1,256),dtype=np.uint8),np.ones((1,256),dtype=np.uint8)])
    logits=integer_forward(test_x,weights)
    (out/'vectors_pixels.hex').write_text(''.join(f'{b:02x}\n'for row in test_x for b in pack_pixels(row)),encoding='ascii')
    (out/'vectors_logits.hex').write_text(''.join(f'{int(v)&0xffffffff:08x}\n'for v in logits.reshape(-1)),encoding='ascii')
    np.savez(out/'validation_vectors.npz',x=test_x,logits=logits)
    manifest={'model':'binary-mlp-256-64-11-v1','weights':int(w1.size+w2.size),'biases':int(b1.size+b2.size),'weight_bits':8,'first_input_bits':1,'hidden_bits':8,'accumulator_bits':32,'shift1':shift,'q1':q1,'q2':q2,'classes':[str(i)for i in range(10)]+['reject'],'seed':314159,'train_count':len(x),'validation_count':len(vx),'training_fonts':[{ 'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in train],'validation_fonts':[str(p)for p in valid],'real_pages_used_for_training':False,'real_reference_is_development_regression_not_generalization_proof':True,'vector_count':len(test_x),'metrics':metrics,'seconds':round(time.monotonic()-start,2),'device':device,'open_source_inspiration':['https://github.com/Akane0721/OrpheusNet','https://github.com/fastmachinelearning/hls4ml']}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in manifest.items()if k in ('model','weights','shift1','metrics','seconds','device')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
