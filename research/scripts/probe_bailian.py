"""A bounded real-audio Bailian probe; never print or save the credential."""
from pathlib import Path
import argparse, json, subprocess, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from score_api.bailian import BailianConfig, transcribe
from score_api.protocol import ApiError


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--audio',type=Path,required=True)
    p.add_argument('--start',type=float,default=4)
    p.add_argument('--duration',type=float,default=8)
    p.add_argument('--key-file',type=Path,default=Path('.score-api/qwen.key'))
    p.add_argument('--base-url',default='https://dashscope.aliyuncs.com/compatible-mode/v1')
    p.add_argument('--model',default='qwen3-asr-flash')
    p.add_argument('--output',type=Path,default=Path('build/bailian_20261030/probe'))
    a=p.parse_args();assert .25<=a.duration<=40 and a.start>=0
    a.output.mkdir(parents=True,exist_ok=True)
    wav=a.output/'selected.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(a.start),'-i',str(a.audio),'-t',str(a.duration),
        '-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)],check=True,capture_output=True)
    start=time.monotonic()
    try:
        value=transcribe(wav.read_bytes(),BailianConfig(str(a.key_file),a.base_url,a.model))
        result={'succeeded':True,**value}
    except ApiError as e:
        result={'succeeded':False,'error_code':e.code,'message':e.message}
    result.update(elapsed_s=round(time.monotonic()-start,3),audio_seconds=a.duration,base_url=a.base_url)
    (a.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['succeeded'] else 2


if __name__=='__main__':sys.exit(main())
