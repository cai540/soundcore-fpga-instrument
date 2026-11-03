"""Pinned official public Whisper checkpoint for local lyric timing research."""
from pathlib import Path
import concurrent.futures,hashlib,http.client,json,time,urllib.request
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029/whisper'
REPO='openai/whisper-large-v3-turbo';REV='41f01f3fe87f28c78e2fbf8b568835947dd65ed9'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(4*1024**2):h.update(b)
    return h.hexdigest()

def main():
    B.mkdir(parents=True,exist_ok=True)
    tree=json.load(urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/tree/{REV}',timeout=30))
    for item in tree:
        name=item['path']
        if item['type']!='file' or name=='.gitattributes':continue
        dst=B/name;size=item['size'];expected=item.get('lfs',{}).get('oid')
        if dst.exists() and dst.stat().st_size==size and (not expected or sha(dst)==expected):continue
        url=f'https://huggingface.co/{REPO}/resolve/{REV}/{name}?research={time.time()}'
        if size<4*1024**2:
            data=urllib.request.urlopen(url,timeout=40).read()
            if len(data)!=size:raise RuntimeError('metadata truncated '+name)
            dst.write_bytes(data);print('saved',name,flush=True);continue
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=40) as response:direct=response.url
        parts=B/(name+'.parts');parts.mkdir(exist_ok=True);chunk=2*1024**2
        def fetch(start):
            end=min(size,start+chunk)-1;target=parts/str(start);n=end-start+1
            if target.exists() and target.stat().st_size==n:return n
            tmp=target.with_suffix('.tmp');data=tmp.read_bytes() if tmp.exists() and tmp.stat().st_size<n else b''
            for retry in range(10):
                try:
                    current=start+len(data)
                    with urllib.request.urlopen(urllib.request.Request(direct,headers={'Range':f'bytes={current}-{end}'}),timeout=40) as response:
                        if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {current}-{end}/'):raise RuntimeError('wrong range')
                        try:data+=response.read()
                        except http.client.IncompleteRead as error:data+=error.partial;tmp.write_bytes(data);continue
                    if len(data)!=n:raise RuntimeError('range truncated')
                    tmp.write_bytes(data);tmp.replace(target);return n
                except Exception as error:
                    print('retry',start,retry+1,type(error).__name__,flush=True)
                    if retry==9:raise
            raise RuntimeError('incomplete part')
        completed=0;last=time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            for future in concurrent.futures.as_completed([pool.submit(fetch,s) for s in range(0,size,chunk)]):
                completed+=future.result()
                if time.monotonic()-last>15 or completed==size:print(name,round(completed/1024**2),'/',round(size/1024**2),'MiB',flush=True);last=time.monotonic()
        joined=dst.with_suffix('.joined')
        with joined.open('wb') as output:
            for s in range(0,size,chunk):
                with (parts/str(s)).open('rb') as source:
                    while data:=source.read(4*1024**2):output.write(data)
        if joined.stat().st_size!=size or (expected and sha(joined)!=expected):raise RuntimeError('official weight SHA256 mismatch')
        joined.replace(dst);print('verified',name,expected,flush=True)
    (B/'provenance.json').write_text(json.dumps({'repo':REPO,'revision':REV,'license':'MIT',
        'files':{q.name:sha(q) for q in B.iterdir() if q.is_file() and q.name!='provenance.json'}},indent=2),encoding='utf8')

if __name__=='__main__':main()
