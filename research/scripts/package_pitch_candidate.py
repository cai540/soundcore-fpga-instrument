"""Export a limited pitch experiment honestly, with before/after audio."""
from pathlib import Path
import hashlib,json,shutil,zipfile
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import render,encode_audio,write_midi
from package_vocal_oss import segment,validate,verify_midi
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_pitch_grounded_20261029'
PRE=R/'build/vocal_syllable_main_20261029';O=R/'output/vocal_pitch_candidate_20261029'
CASES=[('zuguo','我和我的祖国',47090),('chilege','敕勒歌',30970),('qiansixi','牵丝戏',23990),('lantingxu','兰亭序',490)]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    O.mkdir(parents=True,exist_ok=True);media=[];cases=[]
    for name,title,start in CASES:
        d=O/name;d.mkdir(exist_ok=True);src=B/name/'full'
        info=json.loads((src/'result.json').read_text(encoding='utf8'))
        ns=read_notes(src/'melodic_notes.csv');old=read_notes(PRE/name/'full/notes.csv')
        assert [(n['start_ms'],n['duration_ms']) for n in ns]==[(n['start_ms'],n['duration_ms']) for n in old]
        ms=info['source_ms'];validate(ns,ms)
        pcm=np.fromfile(info['input_file'],dtype='<f4')[:ms*16]
        candidate=render(ns,ms);previous=render(old,ms)
        end=min(ms,ns[-1]['start_ms']+ns[-1]['duration_ms']);z=min(end,start+40000)
        media.append(encode_audio(candidate[start*16:end*16],d/'未验收_完整试听.mp3'))
        media.append(encode_audio(np.column_stack([pcm,candidate])[start*16:z*16],d/'前40秒_左人声右候选.mp3'))
        media.append(encode_audio(np.column_stack([previous,candidate])[start*16:end*16],d/'全段_左上次右候选.mp3'))
        if name=='zuguo':
            media.append(encode_audio(candidate[start*16:z*16],d/'前40秒_候选.mp3'))
            media.append(encode_audio(previous[start*16:z*16],d/'前40秒_上次.mp3'))
            media.append(encode_audio(np.column_stack([previous,candidate])[start*16:z*16],d/'前40秒_左上次右候选.mp3'))
        write_midi(ns,d/'候选_完整原时间轴.mid');verify_midi(d/'候选_完整原时间轴.mid',ns)
        clip=segment(ns,start,end);write_midi(clip,d/'候选_试听时间轴.mid');verify_midi(d/'候选_试听时间轴.mid',clip)
        shutil.copy2(src/'melodic_notes.csv',d/'候选_音符.csv')
        shutil.copy2(src/'melodic_audit.json',d/'逐音选音证据.json')
        shutil.copy2(PRE/name/'full/notes.csv',d/'上次v6_音符.csv')
        evidence=d/'pitch_evidence';evidence.mkdir(exist_ok=True)
        for leaf in ['pesto.npz','melodia.npz','pesto.json','melodia.json']:
            shutil.copy2(src/leaf,evidence/leaf)
        audit=json.loads((src/'melodic_audit.json').read_text(encoding='utf8'))
        cases.append({'name':name,'title':title,'changed_pitches':audit['changes'],'notes':len(ns),
                      'all_starts_and_durations_identical':True,'source_pcm_sha256':sha(Path(info['input_file'])),
                      'preview_source_start_ms':start,'preview_source_end_ms':end,
                      'preview_bookmark_is_not_inference_input':True,'listening_accepted':False})
        print('exported',title,audit['changes'],flush=True)
    code=O/'source';code.mkdir(exist_ok=True)
    previous_code=R/'output/vocal_main_syllable_20261029/source'
    for p in previous_code.glob('*'):
        if p.is_file():shutil.copy2(p,code/p.name)
    for leaf in ['melodic_pitch_refiner.py','vocal_pitch_center.py','grounded_pitch_decoder.py','extract_pitch_grounding.py',
                 'extract_melodia_pitch.cjs','transcribe_melodic_pitch.py','run_melodic_candidate.ps1',
                 'test_melodic_pitch_refiner.py','package_pitch_candidate.py']:
        shutil.copy2(R/'scripts'/leaf,code/leaf)
    evidence=O/'diagnostics';evidence.mkdir(exist_ok=True)
    for leaf in ['pitch_error_summary.json','pitch_error_spots.json','diagnostics.json','rejected_lattice_diagnostics.json',
                 'melodic_diagnostics.json','melodia_diagnostics.json','tests.log','cli_smoke_final.log','cli_cache_repeat.log']:
        if (B/leaf).exists():shutil.copy2(B/leaf,evidence/leaf)
    licenses=O/'licenses';licenses.mkdir(exist_ok=True)
    for p in (R/'output/vocal_main_syllable_20261029/licenses').glob('*'):shutil.copy2(p,licenses/p.name)
    shutil.copy2(B/'essentia_js/package/LICENSE',licenses/'ESSENTIA_JS_AGPL3.txt')
    shutil.copy2(B/'extra/pesto_pitch-2.0.1.dist-info/LICENSE.md',licenses/'PESTO_LGPL3.md')
    baseline=json.loads((R/'build/vocal_oss_20261029/baseline_sha256.json').read_text(encoding='utf8'))
    changed=[p for p,h in baseline.items() if sha(R/p)!=h];assert not changed,changed
    smoke=json.loads((B/'cli_smoke/result.json').read_text(encoding='utf8'))
    repeat=json.loads((B/'cli_cache_repeat/result.json').read_text(encoding='utf8'))
    assert repeat['pitch_cache_hit'] and sha(B/'cli_smoke/notes.csv')==sha(B/'cli_cache_repeat/notes.csv')
    validation={'cases':cases,'media':media,'unit_behavior_tests_passed':9,'midi_ms_roundtrips_passed':8,
                'arbitrary_audio_cli_ran':True,'pitch_evidence_cache_reuse_verified':True,
                'cache_repeat_identical_notes':True,'production_android_hash_checks':len(baseline),
                'production_android_changed':changed,'apk_built':False,'fpga_programmed':False,
                'subjective_pitch_quality_accepted':False,'remaining_errors_known':True}
    (O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
    (O/'provenance.json').write_text(json.dumps({'candidate':smoke['version'],'input':'provided separated vocals',
        'new_pitch_evidence_hashes':smoke['pitch_weights_sha256'],'base_weights_sha256':smoke['weights_sha256'],
        'models_not_bundled':True,'default_apk_not_changed':True,
        'official_sources':['https://github.com/SonyCSLParis/pesto','https://github.com/MTG/essentia.js',
                            'https://essentia.upf.edu/reference/std_PredominantPitchMelodia.html']},ensure_ascii=False,indent=2),encoding='utf8')
    report='''# 音高候选核查：仍未达到验收标准

本次只修音高。四首的音符数量、每个起止时刻、休止和分句全部保持上次v6，不靠合并音符掩盖错音。未烧录、未生成或替换APK。手机现有算法仍是原来的版本。

## 试听

《我和我的祖国》目录有前40秒单独候选、上次版本以及“左上次右候选”对照。四首均有完整候选、全段前后对照、前40秒“左人声右候选”。左右声道比较使用同一响度、相同正弦合成器，不是FPGA口琴/二胡音色。

试听起点沿用先前的人声书签，分别位于源文件47.09、30.97、23.99、0.49秒。书签只用来裁切导出，推断不知道曲名、歌词或这些时间；完整CSV和MIDI保留源时钟。

## 真正改动与实际效果

1. 用官方PESTO独立音高观测与Essentia.js PredominantPitchMelodia主旋律观测核对原有RMVPE。主旋律算法只在覆盖充分、另有独立音高/频谱证据时协助改八度；不把几个错八度标签平均成中间音。
2. 对双路都确认的周期颤音估计中心，避免只挑颤音瞬时停留的高点/低点。录音中稳定片段提供弱音级先验；未获稳定证据支持的模糊变化可不采用。没有强制七个自然音，正常、清楚的半音和八度跳进保留。
3. 四首同一套规则实际只改5、2、1、2个音高。祖国有2处半音与3处低八度修正；另外三首改动很少，不能称为音准已经改善到满意程度。没有人工试听验收，也没有识别到真实汉字。
4. 这仍是保守候选，绝不是“修好版”。祖国、牵丝戏和兰亭序仍有错误；敕勒歌两处变更在旧参考覆盖区外，无法靠该参考判断听感是否提升。

## 淘汰了什么

直接采用新基频、连续音高格点重选、保守多模型重选、局部上下文GAME重估、整段统一使用颤音中心等方案都做过检查。部分改正的同时会破坏原来正确的音，未作为交付算法。Essentia主旋律的整段直接量化也会增加半音错误，因此没有整段替换。

诊断目录保留失败结果与最后候选结果。旧编辑谱只用于离线比较，它不是独立真实标注；一致比例不是准确率，更不是听感分数。候选并未解决全部错误。祖国的旧参考稳定区偏差有小幅减少，另外两首覆盖区没有变化，兰亭序没有可靠完整参考，不能报告其准确性。

## 通用入口与缓存

```powershell
& 'D:\\FPGA\\Projects\\soundcore_2026\\scripts\\run_melodic_candidate.ps1' -Audio '录音.mp3'
```

入口实际跑过8秒任意文件路径的解码、冻结v6前端、新的双路音高提取、选音、MIDI和试听导出。再次运行复用了音频内容与权重/提取代码哈希索引的缓存，音符文件相同。修改选音规则不必重跑声学模型。这个8秒运行仅验证通路和缓存，不证明通用音准合格。

## 检查与范围

9项行为测试覆盖：有独立证据的错八度、真实双向八度跳进、弱证据拒绝乱改、不同颤音相位、少见稳定半音、残缺颤音误拟合、无声不提供新证据、真实短音/休止、整体移调。测试不等于音乐听感合格。8份MIDI逐毫秒回读一致，所有MP3经过ffprobe检查，59个Android生产文件哈希未变。

仍为本地Python/Node研究实现；没有迁移至手机，没有更新40秒/512事件限制，没有板上测试。Essentia.js为AGPL-3.0，PESTO为LGPL-3.0；本包保留许可证与来源，不分发模型/WASM权重。若之后集成进APK，需要按实际分发方式处理许可，不能把本候选直接当已发布的App功能。

官方依据：[PESTO](https://github.com/SonyCSLParis/pesto)、[Essentia.js](https://github.com/MTG/essentia.js)、[PredominantPitchMelodia](https://essentia.upf.edu/reference/std_PredominantPitchMelodia.html)。
'''
    (O/'本轮说明_仍未验收.md').write_text(report,encoding='utf8')
    manifest={str(p.relative_to(O)).replace('\\','/'):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='sha256.json'}
    (O/'sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    archive=Path(shutil.make_archive(str(O),'zip',root_dir=O.parent,base_dir=O.name))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf8')
    print('saved',O,'ZIP bytes',archive.stat().st_size,flush=True)

if __name__=='__main__':main()
