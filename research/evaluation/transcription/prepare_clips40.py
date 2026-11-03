"""Freeze source-clock excerpts before algorithm comparison; no note labels."""
from pathlib import Path
import argparse,hashlib,json,subprocess

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',type=Path,default=Path('evaluation/transcription/clips40_phrase_20261030.json'))
    parser.add_argument('--output',type=Path,default=Path('build/vocal_40s_phrase_20261030'))
    args=parser.parse_args();root=args.output;root.mkdir(parents=True,exist_ok=True)
    suite=args.suite
    rows=[]
    for case in json.loads(suite.read_text(encoding='utf8')):
        out=root/'inputs'/case['id'];out.mkdir(parents=True,exist_ok=True)
        args=['ffmpeg','-v','error','-y','-ss',str(case['start_s']),'-t',str(case['duration_s']),'-i',case['audio'],'-ac','1','-ar','44100','-c:a','pcm_f32le',str(out/'source.wav')]
        subprocess.run(args,check=True)
        pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(out/'source.wav'),'-f','f32le','-'])
        assert len(pcm)==40*44100*4
        rows.append({**case,'clip':str(out/'source.wav'),'source_file_sha256':hashlib.sha256(Path(case['audio']).read_bytes()).hexdigest(),'clip_pcm_sha256':hashlib.sha256(pcm).hexdigest(),'samples':len(pcm)//4,'rate':44100,'labels_or_lyrics_used':False})
    (root/'inputs.json').write_text(json.dumps({'suite_sha256':hashlib.sha256(suite.read_bytes()).hexdigest(),'cases':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print('Frozen',len(rows),'clips, 40 seconds each')

if __name__=='__main__':main()
