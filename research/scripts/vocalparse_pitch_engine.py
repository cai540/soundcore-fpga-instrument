"""Audio-only VocalParse adapter with direct local checkpoint loading.

The official checkpoint has full weights, tokenizer, and preprocessor files.
Loading it directly avoids downloading/loading a second base-model copy.
No lyric, score, song name or previously curated MIDI is a model input.
"""
from pathlib import Path
import sys,time,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/vocal_pitch_90_20261029'

class VocalParseEngine:
    def __init__(self,checkpoint=None):
        import torch
        torch.set_num_threads(6);torch.manual_seed(0)
        sys.path.insert(0,str(BASE/'VocalParse'))
        import qwen_asr  # Registers official classes with Transformers.
        from transformers import AutoModel,AutoProcessor,AutoConfig,GenerationConfig
        from safetensors import safe_open
        from vocalparse.model import patch_outer_forward
        from vocalparse.prompts import build_prefix_text
        checkpoint=Path(checkpoint or BASE/'checkpoint')
        if not torch.cuda.is_available():raise RuntimeError('This 1.7B research adapter requires the prepared CUDA environment.')
        self.device=torch.device('cuda:0')
        config=AutoConfig.from_pretrained(str(checkpoint),local_files_only=True)
        # The released checkpoint resizes the AST tokenizer but retains the
        # base padded vocab size in its JSON. Infer the true size from the
        # immutable tensor header, just as upstream load_model does before
        # resizing. Do not mutate the official config file or ignore weights.
        with safe_open(str(checkpoint/'model.safetensors'),framework='pt',device='cpu') as weights:
            rows=[weights.get_slice(k).get_shape()[0] for k in weights.keys() if k.endswith('embed_tokens.weight')]
        if len(rows)!=1:raise RuntimeError('Ambiguous embedding vocabulary in checkpoint.')
        config.thinker_config.text_config.vocab_size=int(rows[0])
        self.model,loading_info=AutoModel.from_pretrained(str(checkpoint),dtype=torch.bfloat16,
            device_map={'':'cuda:0'},attn_implementation='sdpa',local_files_only=True,low_cpu_mem_usage=True,
            output_loading_info=True,config=config)
        if any(loading_info.get(k) for k in ['missing_keys','unexpected_keys','mismatched_keys','error_msgs']):
            raise RuntimeError('Checkpoint/model mismatch: '+repr(loading_info))
        self.processor=AutoProcessor.from_pretrained(str(checkpoint),fix_mistral_regex=True,local_files_only=True)
        if len(self.processor.tokenizer)!=rows[0]:raise RuntimeError('Tokenizer/embedding vocabulary mismatch.')
        patch_outer_forward(self.model);self.model.eval()
        self.model.generation_config=GenerationConfig.from_pretrained(str(checkpoint),local_files_only=True)
        self.prefix=build_prefix_text(self.processor)
        self.revision=json.loads((checkpoint/'upstream_revision.json').read_text(encoding='utf8'))
        self.checkpoint_sha=json.loads((checkpoint/'sha256.json').read_text(encoding='utf8'))['model.safetensors']
        # No supplied ASR/lyric prefix: the checkpoint must infer it from audio.
        assert '<|file_sep|>' not in self.prefix

    def infer(self,pcm,max_tokens=768):
        import torch
        from vocalparse.evaluation import parse_transcription_text
        pcm=np.asarray(pcm,dtype=np.float32)
        if pcm.ndim!=1 or not 1600<=len(pcm)<=30*16000:raise ValueError('Provide mono 16k audio, 0.1 to 30 seconds.')
        start=time.perf_counter();torch.cuda.reset_peak_memory_stats()
        inputs=self.processor(text=[self.prefix],audio=[pcm],sampling_rate=16000,
            return_tensors='pt',padding=False,truncation=False)
        inputs={k:v.to(self.device) for k,v in inputs.items()}
        if 'input_features' in inputs:inputs['input_features']=inputs['input_features'].to(self.model.dtype)
        prefix_len=inputs['input_ids'].shape[1]
        with torch.inference_mode():
            output=self.model.generate(**inputs,max_new_tokens=max_tokens,do_sample=False)
        seq=output.sequences[0] if hasattr(output,'sequences') else output[0]
        ids=seq[prefix_len:];text=self.processor.tokenizer.decode(ids,skip_special_tokens=False)
        parsed=parse_transcription_text(text)
        return {'raw_text':text,'parsed':parsed,'source_pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),
                'source_ms':len(pcm)//16,'tokens':len(ids),'token_limit_reached':len(ids)>=max_tokens,
                'runtime_seconds':time.perf_counter()-start,'peak_cuda_gb':torch.cuda.max_memory_allocated()/1024**3,
                'model_revision':self.revision,'checkpoint_sha256':self.checkpoint_sha,
                'lyrics_or_score_supplied':False,'song_identity_supplied':False}

def main():
    import argparse,subprocess
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=8);a=p.parse_args()
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(a.start),'-i',str(a.audio),'-t',str(a.duration),
                                 '-ac','1','-ar','16000','-f','f32le','-'])
    x=np.frombuffer(raw,dtype='<f4').copy();result=VocalParseEngine().infer(x)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['raw_text']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
