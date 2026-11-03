"""Prepare automatic observations, run the isolated decoder, then evaluate.

Only this evaluation tool reads score labels. The actual decoder is invoked
in a fresh process, receiving an acoustic NPZ and one common configuration.
"""
from pathlib import Path
from dataclasses import asdict
import argparse,csv,hashlib,html,json,subprocess,sys,zipfile,shutil
import numpy as np
from soundcore_audio.articulation import CarrierConfig
from soundcore_audio.pipeline import load_evidence
from soundcore_audio.decoder import tonal_prior
from soundcore_audio.pitch import PitchObserver,interval_likelihood
from soundcore_audio.audio import decode
from tools.decode_vocal_carriers import POLICY
from tools.preview_transcriptions import render,encode,verify_midi
from evaluation.transcription.character_metrics import compare,compare_groups,gate


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_graph(case, output, boundary='original', acoustic=0., content=False):
    # Observer adapters are research-only. No reference text, score or
    # reference-derived timestamps enter this preparation function.
    sys.path.insert(0,str(Path('build/qwen_syllable_20261030').resolve()))
    from partition_characters import prepare
    d=prepare(case)
    if boundary=='content':
        from scipy.signal import find_peaks
        sys.path.insert(0,str(Path('build/vocal_content_20261030').resolve()))
        from ablate import novelty
        with np.load(Path('build/vocal_content_20261030/observations')/case['id']/'content.npz') as q:
            feature=novelty(q['9'])
        feature=np.interp(np.arange(4000)*.01,np.arange(len(feature))*.02+.0125,feature)
        peaks,_=find_peaks(feature,prominence=.15,distance=8)
        d=prepare(case,0.,peaks)
        d['boundary']=np.r_[0.,-feature[d['cuts'][1:-1]],0.]
    if content:
        sys.path.insert(0,str(Path('build/vocal_content_20261030').resolve()))
        from content_segments import cost
        with np.load(Path('build/qwen_syllable_20261030/native_alignment')/case['id']/'phonetic.npz') as q:
            x=q['phone'];t=np.arange(len(x))*float(q['dt'])
        x=np.stack([np.interp(np.arange(4000)*.01,t,x[:,i]) for i in range(2,x.shape[1])],axis=1)
        obs=load_evidence(Path('build/vocal_40s_phrase_20261030/baseline')/case['id']/'observations.npz').phrases[0].observation
        v=cost(x,obs.cuts[:-1],obs.cuts[1:]);scale=max(float(np.median(v[v>.001])),.01)
        a,z=d['cuts'][d['nodes'][:,0]],d['cuts'][d['nodes'][:,1]]
        d['content_cost']=.1*cost(x,a,z)/scale*d['length']*.01/.3
    obs=load_evidence(Path('build/vocal_40s_phrase_20261030/baseline')/case['id']/'observations.npz')
    prior=tonal_prior([p.observation for p in obs.phrases])[0]
    meta={'unit_source':'automatic-source-audio','units':list(d['characters']),
          'pause_after':sorted(d['break_after']),'typical_duration_s':d['nominal_duration'],
          'source_sha256':d['source_hash'],'source_window_s':[case['start_s'],case['start_s']+40],
          'known_reference_text_or_pitches_supplied':False,'forced_alignment_times_used':False,
          'boundary_observer':boundary,'phonetic_content_variance_used':content,
          'observation_adapter_sha256':sha(Path('build/qwen_syllable_20261030/partition_characters.py'))}
    source_observers=Path('build/qwen_syllable_20261030')
    asr=json.loads((source_observers/'transcripts'/case['id']/'transcript.json').read_text(encoding='utf8'))
    phonetic=json.loads((source_observers/'native_alignment'/case['id']/'units.json').read_text(encoding='utf8'))
    meta.update(asr_model_files=asr['model_files'],
                asr_transcript_sha256=sha(source_observers/'transcripts'/case['id']/'transcript.json'),
                phonetic_model_sha256=phonetic['model_sha256'],
                phonetic_observation_sha256=sha(source_observers/'native_alignment'/case['id']/'phonetic.npz'),
                native_observation_sha256=sha(Path('build/vocal_40s_phrase_20261030/baseline')/case['id']/'observations.npz'),
                automatic_unit_times_validated=False,recognized_lyrics_verified=False)
    arrays={'cuts':d['cuts'],'edges':d['nodes'],'carrier':d['carrier'][:,np.arange(128)*2],
            'voiced':d['presence'],'boundary_cost':d['boundary'],'phone_likelihood':d['phones'],
            'pitch_boundary':d['note_probability'],'pitch_prior':prior}
    if content:arrays['content_cost']=d['content_cost']
    if acoustic:
        observer=PitchObserver(Path('.audio_models/pitch'),Path('build/vocal_decoder_refactor_20261030/model_cache'))
        f,c=observer.observe(decode(case['clip'],44100).samples,44100)
        arrays['f0_likelihood']=np.stack([interval_likelihood(f,c,int(d['cuts'][a]),int(d['cuts'][z])) for a,z in d['nodes']])
    np.savez_compressed(output,policy=POLICY,metadata=json.dumps(meta,ensure_ascii=False),**arrays)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--boundary',choices=['original','content'],default='original')
    p.add_argument('--acoustic',type=float,default=0.)
    p.add_argument('--phonetic-content',action='store_true')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    config=CarrierConfig(acoustic_pitch_weight=args.acoustic)
    (args.output/'config.json').write_text(json.dumps(asdict(config),indent=2),encoding='utf8')
    inputs=json.loads(Path('build/vocal_40s_phrase_20261030/inputs.json').read_text(encoding='utf8'))['cases']
    refs=json.loads(Path('evaluation/transcription/character_reference40.json').read_text(encoding='utf8'))['cases']
    refs={c['id']:[u for phrase in c['phrases'] for u in phrase['units']] for c in refs}
    titles={'zuguo':'我和我的祖国','qiansixi':'牵丝戏','chilege':'敕勒歌'}
    rows=[];cards=[]
    for c in inputs:
        out=args.output/c['id'];out.mkdir(exist_ok=True)
        build_graph(c,out/'articulation_evidence.npz',args.boundary,args.acoustic,args.phonetic_content)
        subprocess.run([sys.executable,'-m','tools.decode_vocal_carriers','--evidence',str(out/'articulation_evidence.npz'),
                        '--config',str(args.output/'config.json'),'--output',str(out)],check=True)
        info=json.loads((out/'characters.json').read_text(encoding='utf8'))
        groups=[[n['midi'] for n in u['notes']] for u in info['units']]
        row=compare_groups(refs[c['id']],groups);row['id']=c['id'];row['title']=titles[c['id']]
        row['sequence_only_comparison']=compare(refs[c['id']],[p for group in groups for p in group])
        notes=[{k:int(v) for k,v in n.items()} for n in csv.DictReader((out/'notes.csv').open(encoding='utf8',newline=''))]
        verify_midi(notes,out/'source_clock.mid')
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',c['clip'],'-ar','16000','-ac','1','-f','f32le','-'])
        source=np.frombuffer(raw,dtype='<f4');melody=render(notes,len(source));gain=min(1.,.8/max(float(abs(source).max()),1e-9))
        row['media']=[encode(melody,out/'melody_40s.mp3'),encode(np.column_stack([source*gain,melody]),out/'comparison_40s.mp3')]
        row['source_clock_offset_s']=c['start_s'];row['source_clip_sha256']=sha(c['clip'])
        row['max_notes_per_unit']=max(map(len,groups));row['all_units_one_note']=all(len(g)==1 for g in groups)
        row['notes_csv_sha256']=sha(out/'notes.csv');row['midi_csv_exact_match']=True
        (out/'evaluation.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8');rows.append(row)
        score=f"{row['correct']}/{row['reference_characters']}"
        cards.append(f'<article><h2>{titles[c["id"]]}</h2><p>40 秒 · {len(groups)} 个自动发音单位 · 逐字主音核对 {score}</p><label>算法旋律</label><audio controls src="{c["id"]}/melody_40s.mp3"></audio><label>左原声 / 右算法（耳机对照）</label><audio controls src="{c["id"]}/comparison_40s.mp3"></audio><p class="meta">原始人声 {c["start_s"]}–{c["start_s"]+40} 秒；保留原始节奏与空白，不变速、不移调。</p><a href="{c["id"]}/source_clock.mid">MIDI</a> · <a href="{c["id"]}/characters.json">每字分组与来源</a> · <a href="{c["id"]}/evaluation.json">核对记录</a></article>')
        print(c['id'],score,'groups, max',row['max_notes_per_unit'],flush=True)
    summary={'scope':'40-second-development-snippets-only','gate':gate(rows),'cases':rows,'same_configuration_for_all_clips':True,
             'config':asdict(config),'human_listening_passed':False,'whole_song_accuracy_claimed':False,
             'reference_sha256':sha('evaluation/transcription/character_reference40.json'),
             'core_sha256':sha('soundcore_audio/articulation.py'),'builder_sha256':sha(Path(__file__)),
             'metric_sha256':sha('evaluation/transcription/character_metrics.py'),
             'accepted':False,'apk_updated':False,'fpga_programmed':False}
    (args.output/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>逐字主音 · 40秒对照试听</title><style>body{font:16px/1.7 "Segoe UI","Microsoft YaHei",sans-serif;background:#091723;color:#e8f3f4;max-width:1100px;margin:40px auto;padding:0 24px}h1{font-size:36px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px}article{background:#172f3d;border:1px solid #315260;border-radius:20px;padding:24px}label{display:block;margin-top:22px}audio{width:100%;margin-top:8px}a{color:#53decb}.notice{padding:18px;background:#3a2e20;border-radius:12px;margin:25px 0}.meta{font-size:13px;color:#a0b5c0}</style><h1>逐字主音 · 40 秒对照试听</h1><p>默认一个发音单位一个主音；转音不再要求连续敲出一串碎音。不同字的同音重复发声保留。</p><div class="notice">实验试听，尚未通过 99% / 95% / 95% 验收。这里的数字只核对三个开发片段的逐字简化主音，包含八度；没有验证整曲、逐字起止或主观听感。自动歌词仍有同音误识字。正弦参考音用于比较旋律，不是 FPGA 实录。</div><main>'''+''.join(cards)+'''</main><p>核对按每个发音单位分别进行：不能用前一个字多出的转音顶替后一个字的漏音。允许的简化主音来自提供的谱面；简谱只在生成完结果后用于评价。</p><a href="report.json">完整报告</a><script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    (args.output/'试听与核对.html').write_text(page,encoding='utf8')
    review=args.output/'source_review';review.mkdir(exist_ok=True)
    for directory,pattern in [('soundcore_audio','*.py'),('tests','test_articulation.py'),('tools','decode_vocal_carriers.py'),('evaluation/transcription','character_metrics.py')]:
        target=review/directory;target.mkdir(parents=True,exist_ok=True)
        for f in Path(directory).glob(pattern):shutil.copy2(f,target/f.name)
    shutil.copy2('pyproject.toml',review/'pyproject.toml')
    shutil.copy2('soundcore_audio/README.md',review/'README.md')
    replay='''本包包含自动声学证据、主音解码核心及试听；不包含大模型权重，也不是APK或FPGA固件。
在本目录安装pyproject.toml依赖后，可从缓存独立复算：
python -m tools.decode_vocal_carriers --evidence ../qiansixi/articulation_evidence.npz --config ../config.json --output ../replay_qiansixi
这条命令不读取谱面或研究脚本。重新从MP3识别文字和准备观察器仍是原项目里的实验流程，尚未移植手机。
report.json中的门槛未通过。42项结构检查验证规则与格式，不代表音乐听感或音准已经验收。
'''
    (review/'复算说明.txt').write_text(replay,encoding='utf8')
    with zipfile.ZipFile(args.output/'40秒逐字主音试听与MIDI.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in args.output.rglob('*'):
            if f.is_file() and f.suffix in ['.mp3','.mid','.csv','.json','.html','.npz','.py','.toml','.md','.txt']:z.write(f,f.relative_to(args.output))
    print('gate',summary['gate']['passed'],flush=True)

if __name__=='__main__':main()
