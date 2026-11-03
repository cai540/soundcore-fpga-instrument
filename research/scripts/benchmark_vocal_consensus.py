from pathlib import Path
import csv,json,time
from evaluate_oss_vocals import read_notes
from oss_vocal_consensus import recognize_consensus
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_oss_20261029'
results=[]
for info in json.loads((B/'game_medium_results.json').read_text()):
    name=info['name'];window=info['window'];start=time.perf_counter()
    paths=[B/m/name/window for m in ('game_medium','rosvot','basic')]
    ns=recognize_consensus(*(read_notes(p/'notes.csv') for p in paths),info['source_ms'])
    d=B/'consensus'/name/window;d.mkdir(parents=True,exist_ok=True)
    with (d/'notes.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(ns)
    out={**info,'model':'three trained model sequence consensus; experimental','notes':len(ns),
         'runtime_seconds':time.perf_counter()-start,'upstream_results':[str(p/'result.json') for p in paths],
         'parameters':{'weights':[1.,.7,.7],'switch_cost':5.,'supported_switch_cost':1.2,'grid_ms':10}}
    (d/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');results.append(out)
    print(name,window,len(ns),flush=True)
(B/'consensus_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
