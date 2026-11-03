"""Generic command line for the native-rate single-singer baseline."""
from pathlib import Path
import argparse,json,subprocess,numpy as np
from game_native_voice_engine import NativeVoiceEngine
from transcribe_vocal_oss import write_notes,write_midi
R=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--language',default='zh');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(args.audio),'-ac','1','-ar','44100','-f','f32le','-']),dtype='<f4').copy()
    engine=NativeVoiceEngine(R/'build/vocal_transcription_v9_20261029/native_cache',language=args.language)
    notes,trace=engine.recognize(pcm,44100,lambda i,n:print('chunk',i,'/',n,flush=True))
    write_notes(notes,args.output/'notes.csv');write_midi(notes,args.output/'source_clock.mid')
    (args.output/'trace.json').write_text(json.dumps(trace,indent=2),encoding='utf8')
    print('saved',args.output,'notes',len(notes),'seconds',round(trace['runtime_seconds'],2),flush=True)

if __name__=='__main__':main()
