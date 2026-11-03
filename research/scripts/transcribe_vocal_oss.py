"""General local singing-to-note CLI using the official GAME ONNX models.

Run with the isolated research Python. No song database, lyrics, prior MIDI,
reference scores or hand-edited song clocks are loaded by this entry point.
"""
from pathlib import Path
import argparse,csv,json,subprocess,hashlib,struct
import numpy as np
from game_vocal_engine import GameOnnxEngine

def decode_audio(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4').copy()

def write_notes(ns,path):
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['start_ms','duration_ms','midi','confidence']);w.writeheader();w.writerows(ns)

def render(ns,length_ms):
    out=np.zeros(length_ms*16,dtype=np.float64);phase=0.
    for n in ns:
        a=n['start_ms']*16;count=min(n['duration_ms']*16,len(out)-a)
        if count<=0:continue
        t=np.arange(count)/16000;omega=2*np.pi*440*2**((n['midi']-69)/12)
        env=np.minimum(1,t/.012)*np.minimum(1,(count-np.arange(count))/16000/.018)
        out[a:a+count]+=np.sin(phase+omega*t)*env*.22
        phase=(phase+omega*count/16000)%(2*np.pi)
    return out.astype(np.float32)

def write_midi(ns,path):
    def var(v):
        assert v>=0
        a=[v&127]
        while v>127:v>>=7;a.insert(0,(v&127)|128)
        return bytes(a)
    track=bytearray(b'\0\xff\x51\x03\x07\xa1\x20');cursor=0
    for n in ns:
        assert 0<=n['midi']<=127 and n['duration_ms']>0 and n['start_ms']>=cursor
        track+=var((n['start_ms']-cursor)*2)+bytes([0x90,n['midi'],80])
        track+=var(n['duration_ms']*2)+bytes([0x80,n['midi'],0]);cursor=n['start_ms']+n['duration_ms']
    track+=b'\0\xff\x2f\0'
    path.write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,1000)+b'MTrk'+struct.pack('>I',len(track))+track)

def encode_audio(pcm,path):
    channels=1 if pcm.ndim==1 else pcm.shape[1]
    pcm=(pcm.clip(-1,1)*28000).astype('<i2')
    subprocess.run(['ffmpeg','-v','error','-y','-f','s16le','-ar','16000','-ac',str(channels),'-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(path)],input=pcm.tobytes(),check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    assert int(probe['streams'][0]['channels'])==channels and abs(float(probe['format']['duration'])-len(pcm)/16000)<.2
    return {'file':path.name,'channels':channels,'source_seconds':len(pcm)/16000,'container_seconds':float(probe['format']['duration'])}

def device_fit(ns,source_ms):
    if not ns:return {'eligible':False,'reason':'未识别到音符'}
    low=min(q['midi'] for q in ns);high=max(q['midi'] for q in ns)
    if source_ms>40000:return {'eligible':False,'reason':'目前App/上传曲谱单次40秒限制；整曲结果用于桌面诊断','low_midi':low,'high_midi':high}
    if len(ns)>512:return {'eligible':False,'reason':'超过512音符事件限制'}
    if high-low>71:return {'eligible':False,'reason':'音高跨度超出设备C2至B7；保留原谱，不删低音或钳位','low_midi':low,'high_midi':high}
    lo=36-low;hi=107-high;transpose=max(lo,min(0,hi));degrees=[0,2,4,5,7,9,11]
    return {'eligible':True,'pitch_layout':2,'transpose':transpose,'pitch_range':[low,high],
            'notes':[{'start_ms':q['start_ms'],'duration_ms':q['duration_ms'],'midi':q['midi']+transpose,
                      'note_index':q['midi']+transpose-36,
                      'bank_zero_based':min(4,(q['midi']+transpose-36)//12),
                      'pad_zero_based':max(i for i,d in enumerate(degrees)if d<=(q['midi']+transpose)%12)} for q in ns],
            'note':'仅导出逻辑映射；不是已在手机或FPGA执行的证明'}

def main():
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--size',choices=['small','medium'],default='medium');p.add_argument('--boundary-threshold',type=float,default=.2)
    p.add_argument('--models',type=Path,help='Optional path to one unpacked official GAME ONNX model directory')
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=0);a=p.parse_args()
    pcm=decode_audio(a.audio);begin=round(a.start*16000);end=begin+round(a.duration*16000) if a.duration else len(pcm)
    pcm=pcm[begin:end].astype(np.float32);assert 1600<=len(pcm)<=16000*600
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    model=GameOnnxEngine(size=a.size,boundary_threshold=a.boundary_threshold,model_directory=a.models)
    ns,trace=model.recognize(pcm,lambda i,n:print(f'chunk {i}/{n}',flush=True))
    write_notes(ns,out/'notes.csv');write_midi(ns,out/'melody.mid')
    synth=render(ns,len(pcm)//16)
    media=[encode_audio(synth,out/'melody.mp3'),encode_audio(np.column_stack([pcm,synth]),out/'voice_left_melody_right.mp3')]
    (out/'trace.json').write_text(json.dumps(trace),encoding='utf8')
    info={**trace,'source_name':a.audio.name,'source_offset_seconds':a.start,'pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),
          'media':media,'model_tag':'oss-research-20261029','device':device_fit(ns,len(pcm)//16),
          'not_android_release':True,'not_fpga_timbre':True,'human_listening_accepted':False}
    (out/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',out.resolve(),flush=True)

if __name__=='__main__':main()
