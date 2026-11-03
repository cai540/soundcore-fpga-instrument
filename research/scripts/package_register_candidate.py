"""Auditable partial improvement; explicitly not a 90%-accepted release."""
from pathlib import Path
import hashlib,json,shutil,zipfile
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import render,encode_audio,write_midi
from package_vocal_oss import segment,validate,verify_midi
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029';NEW=R/'build/vocal_pitch_90_20261029'
O=R/'output/vocal_register_candidate_20261029'
CASES=[('zuguo','我和我的祖国',47090),('chilege','敕勒歌',30970),('qiansixi','牵丝戏',23990),('lantingxu','兰亭序',490)]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    O.mkdir(parents=True,exist_ok=True);media=[];cases=[]
    for name,title,bookmark in CASES:
        d=O/name;d.mkdir(exist_ok=True);src=B/name/'full'
        info=json.loads((src/'result.json').read_text(encoding='utf8'));ms=info['source_ms']
        pcm=np.fromfile(info['input_file'],dtype='<f4')[:ms*16]
        notes=read_notes(src/'register_candidate_notes.csv');previous=read_notes(src/'melodic_notes.csv')
        validate(notes,ms);validate(previous,ms)
        synth=render(notes,ms);before=render(previous,ms);end=min(ms,notes[-1]['start_ms']+notes[-1]['duration_ms']);first=min(bookmark+40000,end)
        media.append(encode_audio(synth[bookmark*16:end*16],d/'新版_完整试听.mp3'))
        media.append(encode_audio(synth[bookmark*16:first*16],d/'新版_前40秒.mp3'))
        media.append(encode_audio(np.column_stack([before,synth])[bookmark*16:end*16],d/'全段_左上次候选右新版.mp3'))
        media.append(encode_audio(np.column_stack([pcm,synth])[bookmark*16:end*16],d/'全段_左人声右新版.mp3'))
        write_midi(notes,d/'新版_完整原时间轴.mid');verify_midi(d/'新版_完整原时间轴.mid',notes)
        clip=segment(notes,bookmark,end);write_midi(clip,d/'新版_试听时间轴.mid');verify_midi(d/'新版_试听时间轴.mid',clip)
        shutil.copy2(src/'register_candidate_notes.csv',d/'新版_音符.csv')
        shutil.copy2(src/'melodic_notes.csv',d/'上次候选_音符.csv')
        shutil.copy2(src/'register_candidate_audit.json',d/'逐音选择与分段证据.json')
        cr=json.loads((NEW/name/'full/crepe_input.json').read_text());assert cr['source_pcm_sha256']==sha(Path(info['input_file']))
        cases.append({'name':name,'title':title,'notes_before':len(previous),'notes_after':len(notes),
                      'source_ms':ms,'source_pcm_sha256':sha(Path(info['input_file'])),
                      'preview_start_source_ms':bookmark,'preview_bookmark_used_in_inference':False,
                      'human_listening_accepted':False,'real_world_90_percent_verified':False})
        print('exported',title,len(notes),flush=True)
    diag=O/'diagnostics';diag.mkdir(exist_ok=True)
    for leaf in ['event_comparison.json','register_candidate_results.json','final_behavior_tests.log',
                 'note_metric_tests.log','register_candidate_batch.log','cli_smoke.log','cli_cache_repeat.log','paired_input_diagnostic.json']:
        if (NEW/leaf).exists():shutil.copy2(NEW/leaf,diag/leaf)
    shutil.copy2(B/'register_candidate_frame_diagnostics.json',diag/'stable_frame_comparison_not_accuracy.json')
    for leaf in ['probability_fusion_diagnostics.json','register_probability_diagnostics.json','motif_diagnostics.json']:
        if (B/leaf).exists():shutil.copy2(B/leaf,diag/('rejected_'+leaf))
    srcdir=O/'source';srcdir.mkdir(exist_ok=True)
    for p in (R/'output/vocal_pitch_candidate_20261029/source').glob('*'):
        if p.is_file():shutil.copy2(p,srcdir/p.name)
    for leaf in ['register_candidate_pipeline.py','context_pitch_consensus.py','context_register_decoder.py',
                 'recording_motif_consensus.py','recording_tonality.py','sustained_note_components.py',
                 'unsupported_note_events.py','note_probability_fusion.py','estimate_pitch_contexts.py',
                 'extract_crepe_evidence.py','transcribe_register_candidate.py','run_register_candidate.ps1',
                 'test_register_candidate.py','test_unsupported_note_events.py','test_pitch_note_evaluation.py',
                 'evaluate_pitch_notes.py','evaluate_register_candidate.py','benchmark_register_candidate.py',
                 'game_vocal_engine.py','package_register_candidate.py']:
        shutil.copy2(R/'scripts'/leaf,srcdir/leaf)
    licenses=O/'licenses';licenses.mkdir(exist_ok=True)
    for p in (R/'output/vocal_pitch_candidate_20261029/licenses').glob('*'):
        if p.is_file():shutil.copy2(p,licenses/p.name)
    shutil.copy2(R/'build/vocal_oss_20261029/basic-pitch/LICENSE',licenses/'BASIC_PITCH_APACHE2.txt')
    crepe_licenses=[q for q in (NEW/'venv/Lib/site-packages/torchcrepe-0.0.24.dist-info').rglob('LICENSE*') if q.is_file()]
    if not crepe_licenses:raise RuntimeError('Missing CREPE license')
    shutil.copy2(crepe_licenses[0],licenses/'CREPE_MIT.txt')
    baseline=json.loads((R/'build/vocal_oss_20261029/baseline_sha256.json').read_text(encoding='utf8'))
    changed=[p for p,h in baseline.items() if sha(R/p)!=h];assert not changed,changed
    cold=json.loads((NEW/'cli_smoke/result.json').read_text(encoding='utf8'))
    warm=json.loads((NEW/'cli_cache_repeat/result.json').read_text(encoding='utf8'))
    assert not cold['register_cache_hit'] and warm['register_cache_hit']
    assert sha(NEW/'cli_smoke/notes.csv')==sha(NEW/'cli_cache_repeat/notes.csv')
    batch=json.loads((NEW/'register_candidate_results.json').read_text(encoding='utf8'));assert len(batch)==12
    testlog=(NEW/'final_behavior_tests.log').read_text(encoding='utf8');assert 'Ran 35 tests' in testlog and testlog.rstrip().endswith('OK')
    validation={'cases':cases,'media':media,'full_and_window_cases_run':12,'behavior_tests_passed':35,
                'midi_exact_ms_roundtrips':8,'generic_audio_cli_cold_and_warm_ran':True,
                'warm_cache_reused_identical_notes':True,'production_android_files_checked':len(baseline),
                'production_android_files_changed':changed,'new_apk_built':False,'fpga_programmed':False,
                'real_world_90_percent_verified':False,'known_pitch_and_timing_errors_remain':True}
    (O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    provenance={'candidate':'register-components-research-v7','base_models':cold['weights_sha256'],
        'pitch_models':cold['pitch_weights_sha256'],'additional_models':cold['additional_weights_and_extractor_sha256'],
        'sources':['https://github.com/openvpi/GAME','https://github.com/RickyL-2000/ROSVOT',
                   'https://github.com/SonyCSLParis/pesto','https://github.com/MTG/essentia.js',
                   'https://github.com/spotify/basic-pitch','https://github.com/maxrmorrison/torchcrepe'],
        'models_not_bundled':True,'external_audio_uploads':False,'runtime_song_database':False,
        'vocalparse_not_in_candidate':True,'listening_synthesis':'same neutral sine oscillator and envelope for both versions'}
    (O/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf8')
    report='''# 八度与持续音分段候选：90%目标仍未验收

本轮实际修改的是通用推断。没有用曲名、旧谱、歌词、指定调号或预先修好的音符作为推断输入。四首完整录音、四个独立前40秒片段、四个儿歌片段，共12例都执行同一条流程。没有烧录，没有更新APK。

## 改动

- 分开判断音级和八度。采用GAME完整音节的上下文观测、PESTO/RMVPE连续音高、Basic Pitch多音活动概率与CREPE观测；不平均相差12半音的标签。
- 保留完整音节已经做对的八度，低频周期一致不再自动推翻主旋律。相邻候选一起比较；正常、有支持的真实八度跳进继续保留。
- 同一录音中的重复旋律只作为弱证据，需要周围音符确认移调关系。没有把重复段的高低变化一律复制。
- 恢复被一个过大音节吞掉的持续旋律成分。新成分至少持续220毫秒，并要有独立音高与音符活动支持；清楚的原有短音保持原起止，既有同音重击不会合并。
- 仅删除无有效基频、无连续音高置信支持、音符概率也接近背景的短事件。四首各删除1个这样的事件。未靠大量删音提高比例。
- 缓存依据音频PCM、模型、提取器和边界哈希索引。改解码规则可以继续复用声学计算，8秒任意文件CLI的冷/热运行已实测相同音符结果。

## 当前结果与限制

主要看diagnostics/event_comparison.json的逐音对照，按时间进行一对一匹配，匹配不读取音高。漏音计入分母，八度错也算错；多余音和参考覆盖范围另外列出。参考来自以前的编辑谱，包含人工修改与模型辅助，部分时刻是后段旋律转移，不能把它视作独立真实标注。

《我和我的祖国》旧v6为176/215，新候选190/215，约88.4%；《敕勒歌》177/192变为180/192，约93.8%；《牵丝戏》236/304变为241/304，约79.3%。这些只是旧编辑谱下含漏音的音高一致召回，尚不能叫真实准确率。《兰亭序》缺少可靠完整逐音参考，未报告准确率。四首达到90%的目标没有完成。

稳定区按时长的一致性为祖国94.7%、敕勒歌90.15%、牵丝戏80.76%。此指标排除了参考音符两侧120毫秒，覆盖不完整，不能用来宣称已经做到90%的音符正确。包内同时保留逐音指标与稳定区指标，避免混淆。

仍有错音、漏音、多余事件与时间边界问题，牵丝戏改善较少。也没有人工听感验收。各首仍保留真实源时钟，长间奏没有在研究对照中偷偷裁掉。35项行为测试只能证明边界、颤音、短音、真实八度跳进等规则没有发生已测类型的回归，不是音准达标证明。

## 试听与运行

每首有新版完整试听、前40秒、全段左上次候选右新版、全段左人声右新版、MIDI与逐音CSV。合成音使用相同标准正弦振荡器，方便比较音高节奏，不是FPGA二胡/口琴音色。试听起点是既有的人声书签，仅在导出时裁切，识别过程不知道书签。

项目内通用运行入口：

```powershell
& 'D:\\FPGA\\Projects\\soundcore_2026\\scripts\\run_register_candidate.ps1' -Audio '任意录音.mp3'
```

需要本项目已经准备的CPU和CUDA研究环境。source目录是源码审阅副本，模型不随包分发，不能直接当成可安装APP。现有手机APK仍为0.9。59个Android生产文件哈希检查未变。8份MIDI逐毫秒回读一致，16个试听MP3均通过ffprobe时长/声道检查。

## 已拒绝的分支

VocalParse在部分短段能识别文字，但完整录音中有漏段、无休止重复以及音高偏差；原曲与人声的成对测试都出现过，不能直接把问题归因于分离不纯，因此没有采用。直接使用CREPE整段Viterbi、全曲无条件八度平滑、直接复制重复段、仅根据多音概率重新选音，也有破坏原有正确音的情况，未直接作为候选。

源码与模型来源和许可见provenance.json及licenses。GAME/ROSVOT/CREPE、Basic Pitch、PESTO、Essentia分别按各自许可保留来源；本地研究候选未集成进APK。
'''
    (O/'本轮核查与试听说明.md').write_text(report,encoding='utf8')
    manifest={str(p.relative_to(O)).replace('\\','/'):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='sha256.json'}
    (O/'sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    archive=Path(shutil.make_archive(str(O),'zip',root_dir=O.parent,base_dir=O.name))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf8')
    print('saved',O,'files',len(manifest)+1,'ZIP bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
