"""Audio-derived lyric text and timing, with explicit alignment uncertainty.

The recognizer gets no lyric prompt, title or supplied transcript. Chinese
characters are used only when ASR supplies usable timestamps. Multi-character
word splits are flagged estimates to be acoustically refined downstream.
"""
from pathlib import Path
import argparse,hashlib,json,sys,time,unicodedata
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'


def characters_from_chunks(chunks):
    out=[]
    for chunk in chunks:
        a,z=chunk.get('timestamp',(None,None));text=chunk.get('text','')
        chars=[c for c in text if '\u3400'<=c<='\u9fff']
        if a is None or z is None or z<=a or not chars:continue
        for i,c in enumerate(chars):
            out.append({'char':c,'start_ms':round((a+(z-a)*i/len(chars))*1000),
                        'end_ms':round((a+(z-a)*(i+1)/len(chars))*1000),
                        'asr_word':text,'estimated_split':len(chars)>1,
                        'sentence_end':i==len(chars)-1 and any(q in text for q in '，。！？,!?;；')})
    return out


class LyricAlignmentEngine:
    def __init__(self):
        import torch
        from transformers import AutoModelForSpeechSeq2Seq,AutoProcessor,pipeline
        torch.set_num_threads(6);torch.manual_seed(0)
        self.device='cuda:0' if torch.cuda.is_available() else 'cpu'
        self.dtype=torch.float16 if self.device.startswith('cuda') else torch.float32
        directory=B/'whisper';self.provenance=json.loads((directory/'provenance.json').read_text(encoding='utf8'))
        self.model=AutoModelForSpeechSeq2Seq.from_pretrained(str(directory),local_files_only=True,
                   dtype=self.dtype,low_cpu_mem_usage=True,attn_implementation='eager').to(self.device).eval()
        self.processor=AutoProcessor.from_pretrained(str(directory),local_files_only=True)
        # HF's ASR collator otherwise defaults to space-delimited English
        # when the generation path strips the language token. In Chinese that
        # silently turns a complete lyric line into one "word" timestamp.
        self.processor.tokenizer.language='chinese'
        self.pipe=pipeline('automatic-speech-recognition',model=self.model,tokenizer=self.processor.tokenizer,
                          feature_extractor=self.processor.feature_extractor,device=self.device,dtype=self.dtype)

    def recognize(self,pcm):
        import torch
        pcm=np.asarray(pcm,dtype=np.float32)
        if pcm.ndim!=1 or len(pcm)<1600 or not np.isfinite(pcm).all():raise ValueError('Finite mono PCM required')
        start=time.perf_counter()
        with torch.inference_mode():
            raw=self.pipe({'raw':pcm,'sampling_rate':16000},chunk_length_s=28,stride_length_s=(4,4),batch_size=1,
                 return_timestamps='word',generate_kwargs={'language':'zh','task':'transcribe',
                              'num_beams':3,'do_sample':False,'max_new_tokens':256})
        chars=characters_from_chunks(raw.get('chunks',[]))
        return {'asr':raw,'characters':chars,'characters_count':len(chars),'source_ms':len(pcm)//16,
                'source_pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),'runtime_seconds':time.perf_counter()-start,
                'model':self.provenance['repo'],'revision':self.provenance['revision'],
                'lyrics_prompt_or_song_identity_used':False,'asr_text_is_not_verified_lyrics':True,
                'character_splits_within_multi_character_tokens_are_estimates':True}


def main():
    import subprocess
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=16);args=p.parse_args()
    cmd=['ffmpeg','-v','error','-ss',str(args.start),'-i',str(args.audio)]
    if args.duration>0:cmd+=['-t',str(args.duration)]
    pcm=np.frombuffer(subprocess.check_output(cmd+['-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4').copy()
    result=LyricAlignmentEngine().recognize(pcm);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(result['asr']['text'],'characters',len(result['characters']),'seconds',round(result['runtime_seconds'],2),flush=True)

if __name__=='__main__':main()
