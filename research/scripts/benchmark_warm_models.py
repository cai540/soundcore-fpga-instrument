"""Controlled model-lifetime regression; fixed observed ASR, no answer cache.

Runs are intentionally separate CLI invocations for cold-process comparison.
The fixed transcript is ONLY a benchmark input, never a production fallback.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil,subprocess,sys,time,ctypes

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def rss_mb():
 import psutil
 memory=psutil.Process().memory_info()
 return {'rss_mb':round(memory.rss/2**20,1),'peak_rss_mb':round(memory.peak_wset/2**20,1)}

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['cold','warm']);p.add_argument('songs',nargs='+');p.add_argument('--run',required=True);args=p.parse_args()
 folder=ROOT/'build/warm_models_20261030'/args.run;folder.mkdir(parents=True,exist_ok=False)
 config=json.loads((ROOT/'config/score_api_bailian.json').read_text(encoding='utf8'))
 graphs=ROOT/config['cache']/'graphs';cache=folder/'cache';shutil.copytree(graphs,cache/'graphs');config['cache']=str(cache)
 start=time.perf_counter();resources=None
 if args.mode=='warm':
  from score_api.model_runtime import ModelResources
  resources=ModelResources(config,retain=True);preload=resources.preload()
  preload['including_imports_s']=round(time.perf_counter()-start,4);preload.update(rss_mb())
  print('PRELOAD '+json.dumps(preload),flush=True)
  from score_api.inference import recognize
 else:
  spec=importlib.util.spec_from_file_location('score_api._baseline_worker',ROOT/'build/warm_models_20261030/before/worker.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);recognize=module.recognize
 results=[]
 try:
  for index,song in enumerate(args.songs):
   historical=json.loads((ROOT/f'build/bailian_20261030/{song}_http/http_result.json').read_text(encoding='utf8'))['result']
   characters=historical['recognized_units'];info={k:v for k,v in historical.items() if k.startswith(('algorithm','speech','cloud'))}
   def fixed_speech(pcm,cfg):return characters,info
   import score_api.speech
   score_api.speech.recognize=fixed_speech
   raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/f'build/vocal_40s_phrase_20261030/inputs/{song}/source.wav'),'-ar','44100','-ac','1','-f','f32le','-'])
   assert hashlib.sha256(raw).hexdigest()==historical['source_sha256']
   directory=folder/f'{index}_{song}';directory.mkdir()
   source={k:historical[k] for k in ('source_sample_rate','source_duration_ms','source_sha256','request_id','input_mode')}
   (directory/'source.json').write_text(json.dumps(source),encoding='utf8');(directory/'audio.f32').write_bytes(raw)
   if resources and index:
    # New observation cache for each request; weights/sessions remain resident.
    next_cache=folder/f'cache_{index}';shutil.copytree(graphs,next_cache/'graphs')
    resources.models['game'].cache=next_cache;resources.models['rmvpe'].cache=next_cache
   start=time.perf_counter()
   result=recognize(directory,config,resources=resources,speech_observer=fixed_speech) if resources else recognize(directory,config)
   report={'song':song,'seconds':round(time.perf_counter()-start,4),'notes':len(result['notes']),
    'same_historical_notes':result['notes']==historical['notes'],'timing':result.get('timing'),**rss_mb()}
   results.append(report);(directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
   print('RESULT '+json.dumps(report),flush=True)
  (folder/'report.json').write_text(json.dumps({'mode':args.mode,'fixed_observed_asr':True,'observation_cache_miss_per_request':True,
   'preload':preload if resources else None,'results':results},ensure_ascii=False,indent=2),encoding='utf8')
 finally:
  if resources:resources.close()

if __name__=='__main__':main()
