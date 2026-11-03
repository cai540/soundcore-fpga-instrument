"""One recognizer and one policy for all inputs; no lyric prompts."""
import argparse,hashlib,json
import numpy as np
from local_lyric_alignment import LyricAlignmentEngine,B
from benchmark_oss_vocals import inputs

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',default='');args=p.parse_args()
    e=None
    for name,window,path,_ in inputs():
        if window not in ('full','nursery') or (args.only and args.only not in name):continue
        out=B/'asr'/name/window;out.mkdir(parents=True,exist_ok=True)
        x=np.fromfile(path,dtype='<f4');digest=hashlib.sha256(x.tobytes()).hexdigest()
        f=out/'alignment.json'
        if f.exists() and json.loads(f.read_text(encoding='utf8'))['source_pcm_sha256']==digest:
            print('cached',name,window,flush=True);continue
        if e is None:e=LyricAlignmentEngine()
        print('asr',name,window,flush=True)
        result=e.recognize(x)
        f.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print('done',name,result['characters_count'],round(result['runtime_seconds'],1),result['asr']['text'],flush=True)

if __name__=='__main__':main()
