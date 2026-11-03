"""Raw input A/B: no editorial notes, no melody postprocessor."""
from pathlib import Path
import argparse,hashlib,json,subprocess
import numpy as np
from muscriptor_public_engine import MuscriptorEngine
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v9_20261029'

def main():
    p=argparse.ArgumentParser();p.add_argument('--size',default='medium');p.add_argument('--duration',type=float,default=16);a=p.parse_args()
    engine=MuscriptorEngine(a.size,'float32');results=[]
    for name,file,start in [('zuguo','wodezuguo_vocals_20261026.mp3',47.09),('qiansixi','qiansixi_vocals_20261026.mp3',23.99)]:
        source=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(R/'songs/source'/file),'-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4').copy()
        old=np.fromfile(R/f'build/vocal_oss_20261029/inputs/{name}/full.f32',dtype='<f4')
        begin=round(start*16000);end=begin+round(a.duration*16000)
        for tag,full in [('native',source),('legacy_resampled',old)]:
            pcm=full[begin:end];out=B/'input_ab'/name/tag;out.mkdir(parents=True,exist_ok=True)
            pcm.tofile(out/'input.f32')
            notes,events,midi,info=engine.recognize(pcm,('voice',))
            (out/'raw_notes.json').write_text(json.dumps(notes,indent=2),encoding='utf8');(out/'raw.mid').write_bytes(midi)
            (out/'result.json').write_text(json.dumps(info,indent=2),encoding='utf8')
            results.append({'name':name,'tag':tag,'raw_notes':len(notes),'source_start_s':start,'source_seconds':len(pcm)/16000,'pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest()})
            print(results[-1],flush=True)
    (B/'input_ab/results.json').write_text(json.dumps(results,indent=2),encoding='utf8')

if __name__=='__main__':main()
