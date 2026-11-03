"""Fetch NeuralNote's public GGUF conversion at a pinned, checked revision.

No HF login, gated-source requests or account configuration changes. These are
the public files linked by the NeuralNote and muscriptor.cpp maintainers.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,http.client,json,time,urllib.request
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029/weights'
REPO='DamRsn/muscriptor-gguf';REV='d7045f94e8b19427f4ff9542975035e66596e51c'
FILES={
 'small':(209425152,'925f55af65a20ebc4f8b45ceaf095a12b72493d436cb112623cd0041a1af23d4'),
 'medium':(618442496,'3850cc9e5b436b17a09bd25b8f2615cb3366ab96a71e7b50f73a793a917fdf03'),
 'large':(2739142176,'35a750fb1ab1e77195cdc2c0b9b4aeea2f4d59f11f729f02af9920c4854ef72e')}

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        while block:=source.read(4*1024**2):h.update(block)
    return h.hexdigest()

def fetch(size):
    B.mkdir(parents=True,exist_ok=True);total,expected=FILES[size];name=f'muscriptor-{size}-f16.gguf';dst=B/name
    if dst.exists() and dst.stat().st_size==total and digest(dst)==expected:print('verified cache',name,flush=True);return
    url=f'https://huggingface.co/{REPO}/resolve/{REV}/v1/{name}?download=true'
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:direct=response.url
    parts=B/(name+'.parts');parts.mkdir(exist_ok=True);chunk=2*1024**2
    def part(start):
        end=min(total,start+chunk)-1;target=parts/str(start);length=end-start+1
        if target.exists() and target.stat().st_size==length:return length
        tmp=target.with_suffix('.tmp');data=tmp.read_bytes() if tmp.exists() and tmp.stat().st_size<length else b''
        for attempt in range(10):
            try:
                current=start+len(data)
                req=urllib.request.Request(direct,headers={'Range':f'bytes={current}-{end}'})
                with urllib.request.urlopen(req,timeout=40) as response:
                    if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {current}-{end}/'):
                        raise RuntimeError('Unexpected range response')
                    try:data+=response.read()
                    except http.client.IncompleteRead as error:data+=error.partial;tmp.write_bytes(data);continue
                if len(data)!=length:raise RuntimeError('Truncated range')
                tmp.write_bytes(data);tmp.replace(target);return length
            except Exception as error:
                print('retry part',start,'attempt',attempt+1,'type',type(error).__name__,flush=True)
                if attempt==9:raise
        raise RuntimeError('unfinished range')
    complete=0;last=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        for future in concurrent.futures.as_completed([pool.submit(part,start) for start in range(0,total,chunk)]):
            complete+=future.result()
            if time.monotonic()-last>=15 or complete==total:print(name,round(complete/1024**2),'/',round(total/1024**2),'MiB',flush=True);last=time.monotonic()
    joined=dst.with_suffix('.joined')
    with joined.open('wb') as output:
        for start in range(0,total,chunk):
            with (parts/str(start)).open('rb') as source:
                while block:=source.read(4*1024**2):output.write(block)
    if joined.stat().st_size!=total or digest(joined)!=expected:raise RuntimeError('Published SHA256 mismatch')
    joined.replace(dst)
    (B/(name+'.json')).write_text(json.dumps({'repo':REPO,'revision':REV,'size_bytes':total,'sha256':expected,
       'license':'CC-BY-NC-4.0','public_neuralnote_conversion':True,'login_or_gated_source_used':False},indent=2),encoding='utf8')
    print('SHA256 verified',name,expected,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--size',choices=FILES,default='medium');fetch(p.parse_args().size)
