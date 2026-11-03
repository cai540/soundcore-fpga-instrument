"""Random-initialized project support head; standard MLP/Adam, no fine-tuning.

All training rows must come from generated recordings. Select width and a scalar
temperature using validation only; report held-out test once after selection.
"""
from pathlib import Path
import copy,hashlib,json,math,time
import numpy as np
import torch
from sklearn.metrics import roc_auc_score

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/independent_note_support_20261101'
NAMES=['neural_mean','neural_strong_fraction','neural_relative','neural_winner_fraction',
       'physical_weighted_close','physical_agreement','physical_confidence','physical_voiced_fraction',
       'physical_octave_conflict','physical_distance','relative_rms','duration_seconds_capped']

def bce(y,p):
    p=np.clip(p,1e-7,1-1e-7)
    return float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p)))

def ranking(rows,p):
    groups={}
    for r,s in zip(rows,p):groups.setdefault((r['clip'],r['window']),[]).append((r['y'],float(s)))
    correct=total=0
    for values in groups.values():
        if any(y for y,_ in values):
            total+=1;correct+=max(values,key=lambda a:a[1])[0]
    return dict(correct=int(correct),total=total,fraction=correct/total)

def main():
    start=time.time();torch.set_num_threads(2)
    feature_path=BASE/'data/features.jsonl'
    rows=[json.loads(line) for line in feature_path.read_text(encoding='utf-8').splitlines()]
    manifest=json.loads((BASE/'data/manifest.json').read_text(encoding='utf-8'))
    membership={c['id']:c['split'] for c in manifest['clips']}
    assert all(r['split']==membership[r['clip']] for r in rows)
    sets={s:[r for r in rows if r['split']==s] for s in ['train','validation','test']}
    xs={s:torch.tensor([r['x'] for r in rr],dtype=torch.float32) for s,rr in sets.items()}
    ys={s:torch.tensor([r['y'] for r in rr],dtype=torch.float32)[:,None] for s,rr in sets.items()}
    assert all(torch.isfinite(x).all() and x.min()>=0 and x.max()<=1.00001 for x in xs.values())
    trials=[];models=[]
    for width in [8,16]:
        seed=60317+width;torch.manual_seed(seed)
        net=torch.nn.Sequential(torch.nn.Linear(12,width),torch.nn.ReLU(),torch.nn.Linear(width,1))
        optimizer=torch.optim.Adam(net.parameters(),lr=.012,weight_decay=.0001)
        best=math.inf;checkpoint=None;stale=0;selected_epoch=0
        for epoch in range(1200):
            optimizer.zero_grad();loss=torch.nn.functional.binary_cross_entropy_with_logits(net(xs['train']),ys['train'])
            loss.backward();optimizer.step()
            with torch.no_grad():value=torch.nn.functional.binary_cross_entropy_with_logits(net(xs['validation']),ys['validation']).item()
            if value<best-1e-5:
                best=value;checkpoint=copy.deepcopy(net.state_dict());stale=0;selected_epoch=epoch+1
            else:stale+=1
            if stale>=100:break
        net.load_state_dict(checkpoint)
        with torch.no_grad():logits=net(xs['validation']).numpy().ravel()
        y=ys['validation'].numpy().ravel()
        temperature=min(np.linspace(.6,2.,71),key=lambda t:bce(y,1/(1+np.exp(-np.clip(logits/t,-40,40)))))
        loss=bce(y,1/(1+np.exp(-np.clip(logits/temperature,-40,40))))
        trials.append(dict(width=width,seed=seed,selected_epoch=selected_epoch,validation_bce=loss,temperature=float(temperature)))
        models.append(net)
    chosen=min(range(len(trials)),key=lambda i:trials[i]['validation_bce'])
    trial=trials[chosen];net=models[chosen];temperature=trial['temperature']
    weights=dict(w1=net[0].weight.detach().numpy().tolist(),b1=net[0].bias.detach().numpy().tolist(),
                 w2=net[2].weight.detach().numpy().ravel().tolist(),b2=net[2].bias.item(),temperature=temperature)
    encoded=json.dumps(weights,separators=(',',':')).encode()
    sha=hashlib.sha256(encoded).hexdigest()
    result={}
    for split,rr in sets.items():
        with torch.no_grad():p=torch.sigmoid(net(xs[split])/temperature).numpy().ravel()
        y=ys[split].numpy().ravel();raw=np.asarray([r['x'][0] for r in rr])
        result[split]=dict(rows=len(rr),clips=len(set(r['clip'] for r in rr)),positives=int(y.sum()),
            auc=float(roc_auc_score(y,p)),bce=bce(y,p),brier=float(np.mean((y-p)**2)),
            candidate_ranking=ranking(rr,p),neural_only_ranking=ranking(rr,raw),
            false_accept_at_08=int(((p>=.8)&(y==0)).sum()),accept_at_08=int((p>=.8).sum()))
    folder=BASE/'model';folder.mkdir(exist_ok=True)
    (folder/'weights.json').write_bytes(encoded)
    report=dict(schema=1,architecture=f'12-{trial["width"]}-1 ReLU MLP + sigmoid',features=NAMES,
        parameter_count=sum(p.numel() for p in net.parameters()),random_initialization=True,pretrained_weights_used_for_head=False,
        frontend='Unmodified released CREPE-tiny and YIN/pYIN-style acoustic evidence; not project pretrained weights',
        labels='Known pitches/rests of generated oscillator audio, no teacher model labels or real songs',
        optimizer='standard PyTorch Adam; BCE; weight_decay=0.0001; validation early stopping',
        selection='width and scalar temperature by validation BCE only; test not used for tuning',
        feature_sha256=hashlib.sha256(feature_path.read_bytes()).hexdigest(),weights_sha256=sha,
        generator_sha256=hashlib.sha256(Path(__file__).with_name('generate_note_support_data.py').read_bytes()).hexdigest(),
        trials=trials,selected=trial,metrics=result,torch_version=torch.__version__,seconds=time.time()-start,
        limitation='Synthetic candidate support is not real vocal pitch accuracy or a new pitch foundation model')
    (folder/'training_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    packaged=dict(model='project-candidate-support-v1',features=NAMES,weights_sha256=sha,weights=weights,
        parameter_count=report['parameter_count'],random_initialization=True,
        frontend=report['frontend'],labels=report['labels'],limitation=report['limitation'])
    (ROOT/'app/android/app/src/main/assets/models/note_support.json').write_text(json.dumps(packaged,indent=2),encoding='utf-8')
    def vals(a):return ','.join(format(float(v),'.10g') for v in a)
    lines=['package cn.soundcore.instrument','','import kotlin.math.exp','',
        '/** Project-trained from random initialization on generated PCM, not modified CREPE weights.',
        ' * Standard MLP architecture. See training manifest and third-party provenance ledger. */',
        'internal object NoteSupportModel {',f'    const val WEIGHTS_SHA="{sha}"',
        '    private val w1=arrayOf('+','.join('doubleArrayOf('+vals(row)+')' for row in weights['w1'])+')',
        '    private val b1=doubleArrayOf('+vals(weights['b1'])+')',
        '    private val w2=doubleArrayOf('+vals(weights['w2'])+')',
        '    fun score(features:DoubleArray):Double {',
        '        require(features.size==12 && features.all{it.isFinite() && it in 0.0..1.00001})',
        f'        var logit={weights["b2"]:.10g}',
        '        for(h in w1.indices){var v=b1[h];for(i in features.indices)v+=w1[h][i]*features[i];logit+=w2[h]*maxOf(0.0,v)}',
        f'        return 1/(1+exp(-(logit/{temperature:.10g}).coerceIn(-40.0,40.0)))','    }','}']
    (ROOT/'app/android/app/src/main/java/cn/soundcore/instrument/NoteSupportModel.kt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    fixture=[]
    with torch.no_grad():
        for r in sets['test'][::max(1,len(sets['test'])//48)]:
            p=torch.sigmoid(net(torch.tensor([r['x']],dtype=torch.float32))/temperature).item()
            fixture.append(dict(x=r['x'],expected=p))
    target=ROOT/'app/android/app/src/test/resources/note_support_vectors.json';target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(dict(weights_sha256=sha,vectors=fixture)),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
