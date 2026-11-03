"""NeuralNote's public GGUF weights in the unmodified MuScriptor PyTorch engine.

Only storage tensor names are reversed using the maintainer's exact conversion
map. The published mel bank and Hann window are loaded, and every tensor must
match strictly. No pitch, word boundary, transcript or old score is supplied.
"""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'


def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        while data:=source.read(4*1024**2):h.update(data)
    return h.hexdigest()


class MuscriptorEngine:
    def __init__(self,size='medium',precision='float32'):
        import torch
        from gguf import GGUFReader
        torch.set_num_threads(6);torch.manual_seed(0)
        sys.path.insert(0,str(B/'muscriptor'));sys.path.insert(0,str(B/'muscriptor_cpp'))
        from msl.convert_gguf import _GLOBAL_MAP,_LAYER_MAP
        from muscriptor.transcription_model import _ModelConfig,_build_model,_remap_single_codebook_keys,TranscriptionModel
        from muscriptor.tokenizer.mt3 import MT3Tokenizer
        from fetch_muscriptor_public import FILES,REV,REPO
        self.path=B/'weights'/f'muscriptor-{size}-f16.gguf'
        size_bytes,expected=FILES[size]
        if self.path.stat().st_size!=size_bytes or file_sha(self.path)!=expected:raise RuntimeError('GGUF checksum mismatch')
        self.reader=GGUFReader(str(self.path),mode='r')
        fields=self.reader.fields
        def value(key):return fields[key].contents()
        if value('general.architecture')!='muscriptor' or value('muscriptor.format_version')!=1:raise RuntimeError('Unexpected GGUF contract')
        cfg=_ModelConfig(dim=value('muscriptor.embedding_length'),num_heads=value('muscriptor.attention.head_count'),
                         num_layers=value('muscriptor.block_count'),card=value('muscriptor.vocab_size'))
        self.device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        start=time.perf_counter();saved_dtype=torch.get_default_dtype()
        # Build directly in the intended storage dtype: a 1.4B fp32 CUDA
        # initialization followed by a fp16 cast needlessly doubles peak VRAM.
        if precision not in ('float16','float32'):raise ValueError('Unsupported precision')
        dtype=getattr(torch,precision) if self.device.type=='cuda' else torch.float32
        try:
            torch.set_default_dtype(dtype)
            model=_build_model(self.device,cfg).eval()
        finally:torch.set_default_dtype(saved_dtype)
        # The reference supports fp16 transformer weights with the conditioning
        # path retained in fp32. Match this public option for memory efficiency.
        model.to(device=self.device,dtype=dtype)
        model.condition_provider.float()
        reverse={v[0]:(k,v[2]) for k,v in _GLOBAL_MAP.items()}
        for layer in range(cfg.num_layers):
            for old,(new,_) in _LAYER_MAP.items():reverse[f'blk.{layer}.{new}']=(f'transformer.layers.{layer}.{old}',None)
        state={}
        for tensor in self.reader.tensors:
            if tensor.name not in reverse:raise RuntimeError('Unexpected GGUF tensor '+tensor.name)
            name,transform=reverse[tensor.name]
            array=np.asarray(tensor.data)
            # The only storage-layout transform is the transposed mel bank.
            if transform is not None:array=array.T
            state[name]=torch.from_numpy(np.array(array,copy=True))
        state=_remap_single_codebook_keys(state)
        model.load_state_dict(state,strict=True)
        if any(q.device!=self.device for q in model.parameters()):raise RuntimeError('Mixed parameter devices after model load')
        self.tokenizer=MT3Tokenizer(instrument_vocabulary='MT3_FULL_PLUS',max_shift_steps=1001)
        self.model=TranscriptionModel(model,self.tokenizer,self.device)
        self.info={'model':'MuScriptor','size':size,'gguf_repo':REPO,'gguf_revision':REV,'gguf_sha256':expected,
                   'source_revision':value('muscriptor.source.revision'),'source_sha256':value('muscriptor.source.sha256'),
                   'tensor_count':len(state),'strict_loading':True,'device':str(self.device),
                   'transformer_precision':str(dtype),
                   'conditioning_precision':'float32',
                   'load_seconds':time.perf_counter()-start,'lyrics_score_or_song_identity_used':False,
                   'frontend_uses_published_mel_and_window':True,'sample_rate':16000,'chunk_seconds':5,
                   'license':'CC-BY-NC-4.0','weights_not_retrained':True}
        print('loaded',json.dumps(self.info),flush=True)

    def recognize(self,pcm,instruments=('voice',),progress=lambda *a:None,beam_size=1):
        import torch
        from muscriptor.events import NoteEndEvent,ProgressEvent,NoteStartEvent
        from dataclasses import asdict
        pcm=np.asarray(pcm,dtype=np.float32)
        if pcm.ndim!=1 or len(pcm)<1600 or not np.isfinite(pcm).all():raise ValueError('finite mono 16k PCM is required')
        if self.device.type=='cuda':torch.cuda.reset_peak_memory_stats()
        start=time.perf_counter();notes=[];events=[];raw_events=[]
        with torch.inference_mode():
            for ev in self.model.transcribe((torch.from_numpy(pcm.copy())[None,:],16000),instruments=list(instruments) if instruments else None,
                                            beam_size=beam_size,prelude_forcing=True,batch_size=1,use_sampling=False):
                events.append(ev);raw_events.append({'type':type(ev).__name__,**asdict(ev)})
                if isinstance(ev,ProgressEvent):progress(ev.completed,ev.total)
                elif isinstance(ev,NoteEndEvent):
                    a=round(ev.start_event.start_time*1000);z=min(len(pcm)//16,round(ev.end_time*1000))
                    if z>a:notes.append({'start_ms':a,'duration_ms':z-a,'midi':ev.start_event.pitch,
                                          'confidence':0.,'instrument':ev.start_event.instrument})
        notes.sort(key=lambda n:(n['start_ms'],n['midi']))
        midi=self.model.events_to_midi_bytes(iter(events),beat_grid=None)
        info={**self.info,'source_pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),'source_ms':len(pcm)//16,
              'raw_notes':len(notes),'runtime_seconds':time.perf_counter()-start,'beam_size':beam_size,
              'instrument_constraint':list(instruments) if instruments else None,'greedy_decoding':beam_size==1,
              'source_clock_not_beat_quantized':True,'prelude_forcing':True,
              'peak_gpu_gb':torch.cuda.max_memory_allocated()/1024**3 if self.device.type=='cuda' else None,
              'real_world_accuracy_measured':False}
        return notes,raw_events,midi,info


def main():
    import argparse,subprocess
    p=argparse.ArgumentParser();p.add_argument('audio',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--size',default='medium',choices=['small','medium','large']);p.add_argument('--start',type=float,default=0.)
    p.add_argument('--precision',choices=['float16','float32'],default='float32')
    p.add_argument('--duration',type=float,default=10.);p.add_argument('--automatic-instruments',action='store_true');p.add_argument('--beam-size',type=int,default=1)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-v','error','-ss',str(args.start),'-i',str(args.audio)]
    if args.duration>0:cmd+=['-t',str(args.duration)]
    raw=subprocess.check_output(cmd+['-ac','1','-ar','16000','-f','f32le','-']);pcm=np.frombuffer(raw,dtype='<f4').copy()
    notes,events,midi,info=MuscriptorEngine(args.size,args.precision).recognize(pcm,None if args.automatic_instruments else ('voice',),
                                             lambda i,n:print('chunks',i,'/',n,flush=True),args.beam_size)
    (args.output/'raw_notes.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf8')
    (args.output/'raw_events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf8')
    (args.output/'raw.mid').write_bytes(midi)
    (args.output/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    print('saved',args.output,'notes',len(notes),flush=True)

if __name__=='__main__':main()
