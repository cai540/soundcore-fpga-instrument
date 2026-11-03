"""Package reproducible research results; do not silently call them accepted."""
from pathlib import Path
import csv,hashlib,html,json,shutil,zipfile
import numpy as np
from benchmark_oss_vocals import inputs
from evaluate_oss_vocals import read_notes
from evaluate_pitch_notes import evaluate
from periodic_vowel_events import collapse_periodic_vowels
from transcribe_vocal_oss import write_notes,write_midi,render,encode_audio
from package_vocal_oss import validate,verify_midi,segment
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_transcription_v8_20261029'
O=R/'output/vocal_event_research_20261029'
CASES={'zuguo':('我和我的祖国','wodezuguo',47090),'chilege':('敕勒歌','chilege',30970),
       'qiansixi':('牵丝戏','qiansixi',23990),'lantingxu':('兰亭序',None,490)}
TITLES={**{k:v[0] for k,v in CASES.items()},'tigers':'两只老虎','twinkle':'小星星',
        'tigers_holdout':'两只老虎留出段','twinkle_holdout':'小星星留出段'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def reference(key):
    rows=list(csv.DictReader((R/f'songs/product_song_review/{key}.csv').open(encoding='utf8')))
    return [{'start_ms':round(float(q['source_start_s'])*1000),
             'duration_ms':round((float(q['source_end_s'])-float(q['source_start_s']))*1000),
             'midi':int(q['source_midi'])} for q in rows if int(q['source_midi'])>0]

def main():
    O.mkdir(parents=True,exist_ok=True);rows=[];comparisons=[];media=[]
    for name,window,path,offset in inputs():
        d=B/'runs/medium_voice_beam1'/name/window;out=O/name/window;out.mkdir(parents=True,exist_ok=True)
        pcm=np.fromfile(path,dtype='<f4');ms=len(pcm)//16;digest=hashlib.sha256(pcm.tobytes()).hexdigest()
        schedule=read_notes(d/'melody_lattice.csv');pitched=read_notes(d/'melody_lattice_context.csv')
        assert [(n['start_ms'],n['duration_ms']) for n in schedule]==[(n['start_ms'],n['duration_ms']) for n in pitched]
        signature=hashlib.sha256(json.dumps([(n['start_ms'],n['duration_ms']) for n in schedule]).encode()).hexdigest()
        for w,o in [(4000,0),(4000,2000),(8000,0)]:
            q=np.load(d/f'lattice_game_{w}_{o}.npz')
            assert str(q['source_sha256'])==digest and str(q['boundaries_sha256'])==signature
        e=np.load(R/f'build/vocal_syllable_main_20261029/{name}/{window}/evidence.npz')
        pp=np.load(R/f'build/vocal_pitch_grounded_20261029/{name}/{window}/pesto.npz')
        notes,periodic=collapse_periodic_vowels(pitched,e,pp);validate(notes,ms)
        write_notes(notes,out/'音符.csv');write_midi(notes,out/'原时间轴.mid');verify_midi(out/'原时间轴.mid',notes)
        (out/'周期性颤音审计.json').write_text(json.dumps(periodic,ensure_ascii=False,indent=2),encoding='utf8')
        shutil.copy2(d/'lattice_audit.json',out/'音符区间选择.json')
        shutil.copy2(d/'lattice_context_audit.json',out/'音高选择.json')
        synth=render(notes,ms)
        record={'name':name,'window':window,'title':TITLES[name],'source_ms':ms,'source_offset_seconds':offset,
                'source_pcm_sha256':digest,'notes':len(notes),'periodic_events_removed':periodic['events_removed'],
                'lyrics_or_editorial_score_used_in_inference':False,'real_world_90_percent_verified':False}
        if window=='full':
            title,refkey,bookmark=CASES[name]
            begin=notes[0]['start_ms'] if notes else 0;end=notes[-1]['start_ms']+notes[-1]['duration_ms'] if notes else ms
            media.append(encode_audio(synth[begin*16:end*16],out/'完整试听.mp3'))
            first=min(ms,bookmark+40000)
            media.append(encode_audio(synth[bookmark*16:first*16],out/'前40秒.mp3'))
            media.append(encode_audio(np.column_stack([pcm[:ms*16],synth])[bookmark*16:end*16],out/'全段_左人声右识谱.mp3'))
            old=read_notes(R/f'build/vocal_pitch_grounded_20261029/{name}/full/register_candidate_notes.csv')
            previous=render(old,ms)
            media.append(encode_audio(np.column_stack([previous,synth])[bookmark*16:first*16],out/'前40秒_左上版右本轮.mp3'))
            clip=segment(notes,bookmark,first);write_midi(clip,out/'前40秒.mid');verify_midi(out/'前40秒.mid',clip)
            record.update(preview_bookmark_source_ms=bookmark,bookmark_used_in_inference=False,
                          full_audition_start_source_ms=begin,full_audition_end_source_ms=end)
            if refkey:
                ref=reference(refkey);current=evaluate(ref,notes);before=evaluate(ref,old)
                (out/'旧编辑稿代理对照_不是独立准确率.json').write_text(json.dumps({'previous':before,'current':current},ensure_ascii=False,indent=2),encoding='utf8')
                comparisons.append({'name':name,'title':title,'before':before,'current':current})
        else:media.append(encode_audio(synth,out/'试听.mp3'))
        (out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');rows.append(record)
        print('exported',name,window,len(notes),flush=True)
    baseline=json.loads((R/'build/vocal_oss_20261029/baseline_sha256.json').read_text(encoding='utf8'))
    changed=[q for q,h in baseline.items() if sha(R/q)!=h];assert not changed,changed
    cold=json.loads((B/'cli_final_cold/result.json').read_text(encoding='utf8'))
    warm=json.loads((B/'cli_final_warm/result.json').read_text(encoding='utf8'))
    assert cold['acoustic_cache_hit'] is False and warm['acoustic_cache_hit'] is True
    assert cold['source_pcm_sha256']==warm['source_pcm_sha256']
    assert sha(B/'cli_final_cold/notes.csv')==sha(B/'cli_final_warm/notes.csv')
    assert sha(B/'cli_final_cold/source_clock.mid')==sha(B/'cli_final_warm/source_clock.mid')
    tests=(B/'final_behavior_tests.log').read_text(encoding='utf8');assert 'Ran 22 tests' in tests and tests.rstrip().endswith('OK')
    diagnostics=O/'diagnostics';diagnostics.mkdir(exist_ok=True)
    for f in ['final_behavior_tests.log','policy_diagnostics.json','final_lattice_batch.log','final_contexts.log',
              'cli_final_cold.log','cli_final_warm.log','periodic_vowels.log','full_asr.log']:
        if (B/f).exists():shutil.copy2(B/f,diagnostics/f)
    (diagnostics/'fair_previous_comparison.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2),encoding='utf8')
    src=O/'source_review';src.mkdir(exist_ok=True)
    files=['muscriptor_public_engine.py','monophonic_note_lattice.py','transcription_event_consensus.py',
           'periodic_vowel_events.py','vocal_pitch_center.py','recording_tonality.py','monophonic_event_path.py',
           'note_probability_fusion.py','estimate_pitch_contexts.py','game_vocal_engine.py','syllable_vocal_evidence.py',
           'syllable_vocal_decoder.py','extract_pitch_grounding.py','extract_crepe_evidence.py',
           'transcribe_event_candidate.py','run_event_candidate.ps1','transcribe_vocal_oss.py','package_vocal_oss.py',
           'evaluate_pitch_notes.py','test_pitch_note_evaluation.py','test_note_lattice.py','test_periodic_vowel_events.py',
           'fetch_muscriptor_public.py','fetch_whisper_public.py','local_lyric_alignment.py','phonetic_event_refinement.py',
           'benchmark_muscriptor.py','benchmark_note_lattice.py','estimate_lattice_contexts.py','package_event_candidate.py']
    for f in files:shutil.copy2(R/'scripts'/f,src/f)
    license_dir=O/'licenses';license_dir.mkdir(exist_ok=True)
    for p in (R/'output/vocal_register_candidate_20261029/licenses').iterdir():
        if p.is_file() and 'ESSENTIA' not in p.name:shutil.copy2(p,license_dir/p.name)
    shutil.copy2(B/'muscriptor/LICENSE',license_dir/'MUSCRIPTOR_CODE_MIT.txt')
    shutil.copy2(B/'muscriptor_cpp/LICENSE',license_dir/'MUSCRIPTOR_CPP_MIT.txt')
    shutil.copy2(B/'gguf_readme.txt',license_dir/'MUSCRIPTOR_WEIGHTS_CC_BY_NC_4.0_MODEL_CARD.txt')
    validation={'cases':rows,'media':media,'model_inferences_per_size':12,'sizes_actually_run':['small','medium','large'],
                'selected_runtime_sizes':['medium','large'],'behavior_tests':22,'midi_roundtrips':16,
                'generic_cli_ran_on_holdout':True,'cold_and_warm_identical_notes_and_midi':True,
                'renaming_audio_does_not_change_result':True,'production_files_checked':len(baseline),'production_files_changed':changed,
                'apk_version':'0.9-vocal-contours','new_apk_built':False,'fpga_programmed':False,
                'release_gate_passed':False,'real_world_90_percent_verified':False,
                'known_pitch_count_and_timing_errors_remain':True,'not_an_accepted_release':True}
    (O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    provenance={'local_cli_weights_and_extractor_hashes':cold['weights_and_extractor_sha256'],
                'primary_model_info':json.loads((B/'runs/medium_voice_beam1/zuguo/full/result.json').read_text()),
                'alternate_model_info':json.loads((B/'runs/large_voice_beam1/zuguo/full/result.json').read_text()),
                'evaluation':{'references_are_old_editorial_proxies':True,'lan_full_reference_available':False,
                              'pitch_blind_chronological_matching':True,'missing_notes_count_against_recall':True,
                              'extra_notes_count_against_precision':True},
                'inference_reads_supplied_lyrics_or_score_or_old_midi':False,
                'source_code_copies_are_review_material_models_not_bundled':True}
    (O/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf8')
    metric_rows=''
    for c in comparisons:
        a=c['before'];b=c['current'];den=b['reference_voiced_notes']
        metric_rows+=f'<tr><td>{c["title"]}</td><td>{a["correct_pitch_and_octave_notes"]}/{den}</td><td>{b["correct_pitch_and_octave_notes"]}/{den}</td><td>{a["missed_notes"]} → {b["missed_notes"]}</td><td>{a["extra_notes_inside_outer_reference_span"]} → {b["extra_notes_inside_outer_reference_span"]}</td></tr>'
    audio_html=''
    for name,(title,_,_) in CASES.items():
        d=f'{name}/full'
        audio_html+=f'<section><h2>{title}</h2><p>本轮前40秒：<audio controls preload="none" src="{d}/前40秒.mp3"></audio></p><p>左声道人声、右声道识谱：<audio controls preload="none" src="{d}/全段_左人声右识谱.mp3"></audio></p><p><a href="{d}/完整试听.mp3">完整试听</a> · <a href="{d}/前40秒_左上版右本轮.mp3">左上版、右本轮</a> · <a href="{d}/原时间轴.mid">完整MIDI</a> · <a href="{d}/音符.csv">逐音数据</a></p></section>'
    report='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>通用识谱第8轮检查记录</title><style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;max-width:1050px;margin:35px auto;padding:0 22px;line-height:1.8;color:#182b38;background:#f7f9fb}h1{font-size:27px}h2{font-size:20px}section,.card{background:white;border:1px solid #d7e0e5;border-radius:12px;padding:20px;margin:20px 0}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ced9df;text-align:left}audio{vertical-align:middle;width:min(100%,480px)}.status{background:#fff2d8;border-left:5px solid #ba801b;padding:16px}code{background:#e8eef2;padding:2px 5px}a{color:#17668c}</style><h1>通用录音识谱：本轮代码与对照试听</h1>
<div class="status"><b>状态：仍未达到验收要求，没有验证“90%音高正确”。没有更新APK，没有烧录。</b><br>四首歌使用同一个通用流程。旧曲谱、旧歌词和手工MIDI只用于离线比较，不进入识谱。不能用行为测试通过或模型置信度来代替听感验收。</div>
<div class="card"><h2>实际更改</h2><ol><li>运行NeuralNote所采用的MuScriptor完整音符事件模型，记录音高、起音、结束和跨5秒窗口的持续音状态。small、medium、large均实际跑了12个输入，最终候选采用medium与large，未把“大模型一定更准”作为依据。</li><li>用完整音符区间组成单旋律候选图。迟到的低八度成分不再强制截断长音；模型间几十毫秒的起音偏差先对齐，不作为两次演奏。</li><li>修复前音估长后吞掉句中短音的错误；保留真实同音重击、短音、半音、八度跳进和休止。</li><li>分别判断预期音高与实际人声颤动。只有两条连续音高观察都能解释为同一个周期性颤音，且没有新的发音起点时，才合并碎片。</li><li>保存原始波形哈希、模型版本和声学数据。修改后续解码不必重跑录音；缓存命中与更换文件名的一致性已经实际检查。</li></ol></div>
<div class="card"><h2>公平对照：仍有明显未解决的问题</h2><p>下表与上次实际提供的v7候选比较，不只与一个很弱的新模型基线比较。参考是旧编辑谱代理，具有误差，且部分片段没有完整标注。因此表格不是本功能真实准确率；“多余音”只统计参考外框内的候选，未标注片段另列在JSON中。</p><table><tr><th>录音</th><th>上版音高和八度均匹配</th><th>本轮匹配</th><th>漏配</th><th>参考区间内额外音</th></tr>'''+metric_rows+'''</table><p>《兰亭序》没有可靠的全曲独立标注，不编造其准确率。音准、音符数量和节奏仍需同时改进；本轮没有全面达到发布门限。</p></div>
<div class="card"><h2>已排除的方案</h2><p>Whisper官方模型已在本地实际运行，但在长音、戏腔与间奏中出现重复“啦”及无关文字，不能拿其字数作为音符数量。中文token时间聚合问题已修正，但ASR不进入最终候选的强制切分。较大/较小转谱模型的单独替换、直接重复段投票以及过强合并均出现退步，未作为发布方案。</p></div>
<div class="card"><h2>实际检查</h2><p>4首完整录音、4段独立前40秒和4段儿歌/留出段均已运行。22项行为与计数口径测试通过，16份MIDI逐毫秒回读一致。独立8秒留出录音CLI冷启动和改名后缓存运行的音符与MIDI一致。59份Android生产文件哈希保持一致。这些是软件检查，不是上板结果，也不是90%音准证明。</p></div>'''+audio_html+'''
<div class="card"><h2>可运行入口与模型来源</h2><p>原工程入口：<code>scripts/run_event_candidate.ps1 -Audio 输入.wav -Output 输出目录</code>。需要本项目已经准备好的两个独立Python环境、公开模型和GPU。本压缩包的source_review是审阅副本，模型没有打包；尚未移植到手机端，不能把本地桌面推断当成新版APK的功能。</p><p>最符合所述“分析软件原理”项目的是 <a href="https://github.com/morluto/rea">REA</a>。本轮直接阅读并运行的转谱源码来自 <a href="https://github.com/DamRsn/NeuralNote">NeuralNote</a>、<a href="https://github.com/muscriptor/muscriptor">MuScriptor</a> 和 <a href="https://github.com/DamRsn/muscriptor.cpp">muscriptor.cpp</a>。公开转换权重来自 <a href="https://huggingface.co/DamRsn/muscriptor-gguf">维护者GGUF仓库</a>，完整SHA256已校验；ASR来自 <a href="https://huggingface.co/openai/whisper-large-v3-turbo">OpenAI官方Whisper</a>。没有安装REA服务或反编译闭源软件。</p><p>MuScriptor代码MIT，权重CC BY-NC 4.0；PESTO等组件的许可证保留在licenses。当前作为本地研究候选，权重未进入APK。试听采用中性合成音，不代表FPGA的口琴、二胡音色。</p></div></html>'''
    (O/'验收检查.html').write_text(report,encoding='utf8')
    manifest={str(p.relative_to(O)).replace('\\','/'):{'size':p.stat().st_size,'sha256':sha(p)} for p in O.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (O/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    for relative,info in manifest.items():assert sha(O/relative)==info['sha256']
    archive=O.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as zipf:
        for f in O.rglob('*'):
            if f.is_file():zipf.write(f,f.relative_to(O.parent))
    with zipfile.ZipFile(archive) as zipf:assert zipf.testzip() is None
    print('validated',len(manifest),'files',len(media),'audio files','zip_bytes',archive.stat().st_size,flush=True)
    print('proxy_counts',[(c['name'],c['current']['correct_pitch_and_octave_notes'],c['current']['reference_voiced_notes']) for c in comparisons],flush=True)

if __name__=='__main__':main()
