"""Package the generic main-note candidate, including failures and checks."""
from pathlib import Path
import csv,hashlib,importlib.metadata,json,shutil,zipfile
import numpy as np
from evaluate_oss_vocals import read_notes
from transcribe_vocal_oss import write_midi,write_notes,render,encode_audio
from package_vocal_oss import segment,validate,verify_midi
R=Path(__file__).resolve().parents[1];B=R/'build/vocal_syllable_main_20261029';OLD=R/'build/vocal_oss_20261029'
O=R/'output/vocal_main_syllable_20261029'
CASES=[('zuguo','我和我的祖国',47090),('chilege','敕勒歌',30970),('qiansixi','牵丝戏',23990),('lantingxu','兰亭序',490)]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    O.mkdir(exist_ok=True);media=[];cases=[]
    diagnostics=json.loads((B/'diagnostics.json').read_text(encoding='utf8'))
    for name,title,start in CASES:
        src=B/name/'full';d=O/name;d.mkdir(exist_ok=True)
        info=json.loads((src/'result.json').read_text());ns=read_notes(src/'notes.csv')
        pcm=np.fromfile(info['input_file'],dtype='<f4');ms=info['source_ms'];pcm=pcm[:ms*16]
        validate(ns,ms);write_midi(ns,d/'主音版_完整原时间轴.mid');verify_midi(d/'主音版_完整原时间轴.mid',ns)
        shutil.copy2(src/'notes.csv',d/'主音版_音符.csv')
        shutil.copy2(src/'syllable_audit.json',d/'声学音节与边界证据.json')
        shutil.copy2(src/'evidence.npz',d/'连续音高与字界缓存.npz')
        shutil.copy2(src/'evidence.json',d/'输入说明.json')
        synth=render(ns,ms)
        prior=read_notes(OLD/'game_medium'/name/'full/notes.csv');old_synth=render(prior,ms)
        end=min(ms,ns[-1]['start_ms']+ns[-1]['duration_ms']);clip=segment(ns,start,end)
        write_midi(clip,d/'主音版_人声段试听.mid');verify_midi(d/'主音版_人声段试听.mid',clip)
        media.append(encode_audio(synth[start*16:end*16],d/'主音优先_完整试听.mp3'))
        media.append(encode_audio(np.column_stack([pcm,synth]),d/'全文件_左人声右主音.mp3'))
        media.append(encode_audio(np.column_stack([old_synth,synth])[start*16:end*16],d/'全段对照_左上次右本次.mp3'))
        z=min(ms,start+40000)
        media.append(encode_audio(np.column_stack([pcm,synth])[start*16:z*16],d/'前40秒_左人声右主音.mp3'))
        if name=='zuguo':
            a=start+40000;z=min(ms,a+40000)
            media.append(encode_audio(np.column_stack([pcm,synth])[a*16:z*16],d/'第41至80秒_左人声右主音.mp3'))
        row={**info,'title':title,'preview_start_source_ms':start,'preview_end_source_ms':end,
             'preview_bookmark_not_recognizer_input':True,'source_clock_preserved':True,
             'human_listening_accepted':False,'not_android_release':True,'not_fpga_timbre':True}
        (d/'候选说明.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8');cases.append(row)
        for model in ['syllable_main','game','old_0.9']:
            p=B/f'{name}_{model}_word_audit.json'
            if p.exists():shutil.copy2(p,d/f'离线参考字界对照_{model}.json')
        print('exported',title,len(ns),flush=True)
    code=O/'source';code.mkdir(exist_ok=True)
    for leaf in ['syllable_vocal_decoder.py','syllable_vocal_evidence.py','transcribe_syllable_main.py','run_syllable_transcription.ps1',
                 'benchmark_syllable_main.py','evaluate_syllable_main.py','audit_oss_syllables.py','reestimate_syllable_pitch.py',
                 'finalize_syllable_pitch.py','test_syllable_vocal_decoder.py','game_vocal_engine.py','transcribe_vocal_oss.py',
                 'benchmark_oss_vocals.py','evaluate_oss_vocals.py','oss_vocal_postprocess.py','package_vocal_oss.py','package_syllable_main.py']:
        shutil.copy2(R/'scripts'/leaf,code/leaf)
    for leaf in ['diagnostics.json','results.json','v1_diagnostics.json','v2_diagnostics.json','v3_diagnostics.json','v4_diagnostics.json','v5_diagnostics.json',
                 'tests.log','extract.log','cli_final.log','cli_cache_repeat.log']:
        if (B/leaf).exists():shutil.copy2(B/leaf,O/leaf)
    licenses=O/'licenses';licenses.mkdir(exist_ok=True)
    for repo in ['GAME','ROSVOT']:shutil.copy2(OLD/repo/'LICENSE',licenses/f'{repo}_LICENSE')
    shutil.copy2(B/'extra/torchfcpe-0.0.4.dist-info/LICENSE',licenses/'FCPE_LICENSE')
    baseline=json.loads((OLD/'baseline_sha256.json').read_text(encoding='utf8'))
    changed=[p for p,h in baseline.items() if sha(R/p)!=h];assert not changed,changed
    smoke=json.loads((B/'cli_final/result.json').read_text(encoding='utf8'))
    repeat=json.loads((B/'cli_cache_repeat/result.json').read_text(encoding='utf8'))
    assert repeat['inference_cache_hit'] and sha(B/'cli_final/notes.csv')==sha(B/'cli_cache_repeat/notes.csv')
    (O/'validation.json').write_text(json.dumps({'media':media,'all_midi_exact_ms_roundtrip':True,'source_clocks_nonoverlap_valid':True,
          'behavior_tests_passed':10,'arbitrary_audio_file_cli_ran':True,'repeat_cache_hit':True,'repeat_notes_identical':True,
          'production_files_hash_checked':len(baseline),'production_files_changed':changed,'human_listening_accepted':False,
          'phone_or_fpga_tested':False},ensure_ascii=False,indent=2),encoding='utf8')
    fcpe_weight=B/'extra/torchfcpe/assets/fcpe_c_v001.pt'
    (O/'provenance.json').write_text(json.dumps({'candidate_version':'syllable-main-v6-evidence1','cases':cases,
          'models':['https://github.com/RickyL-2000/ROSVOT','https://github.com/openvpi/GAME','https://github.com/CNChTu/FCPE'],
          'weight_hashes':smoke['weights_sha256'],'fcpe_wheel_sha256':sha(B/'torchfcpe-0.0.4-py3-none-any.whl'),
          'fcpe_weight_sha256':sha(fcpe_weight),'weights_not_bundled':True,
          'input_is_separated_vocals_not_mixed_original_audio':True},ensure_ascii=False,indent=2),encoding='utf8')
    # The report presents both improvements and remaining regressions. These
    # diagnostics are not independent transcription accuracy or listening scores.
    table=[]
    for name,title,_ in CASES:
        old=next(q for q in diagnostics if q['name']==name and q['model']=='game')
        new=next(q for q in diagnostics if q['name']==name and q['model']=='syllable_main')
        acc=(f"{old['reference_interior_pitch_agreement']:.2%} → {new['reference_interior_pitch_agreement']:.2%}" if 'reference_interior_pitch_agreement' in new else '无可靠完整参考，不给准确率')
        table.append(f"| {title} | {old['under_200ms']} → {new['under_200ms']} | {old.get('extra_word_pitch_changes','—')} → {new.get('extra_word_pitch_changes','—')} | {acc} |")
    report='''# 主音优先的通用人声转谱候选

本轮目标：一个估计的声学音节通常保留一个稳定主音，以原来的持续时间、重复起音和句间休止表现节奏。只保留极少数有持续平台证据的双音装饰。版本：syllable-main-v6-evidence1。没有生成APK或烧录。

## 试听

四个子目录中的“主音优先_完整试听.mp3”是本次结果；“全段对照_左上次右本次.mp3”左右分别为上一轮GAME候选和本次主音优先候选；“全文件_左人声右主音.mp3”从原文件开头保留全部时间轴，便于核对错误、停顿和残留。

| 曲目 | 本轮完整试听 |
|---|---|
| 我和我的祖国 | [试听](zuguo/主音优先_完整试听.mp3) |
| 敕勒歌 | [试听](chilege/主音优先_完整试听.mp3) |
| 牵丝戏 | [试听](qiansixi/主音优先_完整试听.mp3) |
| 兰亭序 | [试听](lantingxu/主音优先_完整试听.mp3) |

声音统一用相同正弦合成器生成，便于直接比较旋律、音高和节奏，不是板上的口琴或二胡音色。前40秒之后也已完整计算，并另导出祖国第41至80秒对照。从先前已定位的人声起点计时，分别是原文件47.09、30.97、23.99、0.49秒；这些数字只用于试听书签，不参与算法。全文件对照/MIDI/CSV完整保留开头和尾部。内部没有删掉真实休止，也没有按歌重排节拍。

## 本次真正改变的部分

1. 分段以ROSVOT的RWBD声学字界为主要证据，结合稳定的音高平台恢复漏检字界；不把每个小滑音当新音。
2. 每个估计音节独立挑主音。GAME音符证据、RMVPE连续音高、官方FCPE交叉证据共同参与；FCPE也有低八度错误，不能直接当真值。
3. 用频谱中奇/偶次谐波的支持度识别部分半频误判，再用有限的旋律连续性约束选音。保留真实的持续八度跳进，没有一律限制音程。
4. 同一录音里明确、稳定的音级形成一个很弱的先验，只协助处理模糊的半音；不指定调号，也不把输出硬掰成七个自然音。清楚的少见半音有专门保护测试。
5. 字内通常一个主音；允许的装饰最多把一个估计音节分为两音，要求两侧各有至少240ms的稳定平台、模型也支持，且最多占估计音节数的1/8。词界补偿仍是声学近似，不能承诺真实每个汉字都严格受这个上限约束。
6. 弱尾音按当前有声段自己的音量收尾，不用全文件最大音量删除安静字；真实短休止、同音重复字和有清楚声学证据的140ms短字保留。

推断没有读取曲名、旧歌词、旧MIDI、旧手工谱，也没有对“某首歌的某个字”设置例外。只读取音频、通用声学权重与从音频计算的证据。

## 对照数据

| 曲目 | 短于200ms的音符：上次→本次 | 旧参考字内额外变音：上次→本次 | 旧编辑谱部分稳定内部音高一致性 |
|---|---:|---:|---|
'''+ '\n'.join(table)+'''

这些只是旧编辑谱的部分稳定片段对照，不是准确率、听感分数或独立基准。参考本身含手工选择和先前模型辅助；字的时间边界也可能有误差。“短音减少”同样不等于正确：本轮早期版本曾错误吞掉正常音，后来已补充稳定平台恢复，保留了10项行为测试和迭代对照。

仍有重要局限：祖国依然有半音/低八度疑点；牵丝的字界、漏音和休止还有明显问题；敕勒歌本轮部分稳定音高对照仍低于更早0.9的90.62%。本次不能称为全四首质量已经合格。没有人类逐句试听验收结果，human_listening_accepted一直为false。

额外尝试：把整个声学音节重新送GAME音高估计器重估，在第二阶段对祖国反而退步，未放入最终候选；对应文件标记reestimate_v2_rejected。RMVPE原来的900Hz后过滤可能丢失高音证据，本次另保留原范围，但不能把所有八度错误归因于这一个参数。

## 通用入口与缓存

这台电脑上可执行：

```powershell
& 'D:\\FPGA\\Projects\\soundcore_2026\\scripts\\run_syllable_transcription.ps1' -Audio '录音路径.mp3'
```

入口实际跑过音频解码、模型推断、主音解码、MIDI和MP3导出；重复运行命中了模型缓存且音符结果逐字节相同。缓存按实际PCM哈希、模型权重哈希与证据版本索引，保存在build/vocal_syllable_main_20261029/local_cache；后续修改主音解码不必重新运行声学模型。模型权重变更、音频变更则分开保存，避免复用错误数据。

四首全文件、四个首40秒和四个儿歌窗口均已重算；后两份儿歌窗口来自已有录音的不同片段，不是全新歌手的独立泛化集。本轮输入只用提供的分离人声，没有用原曲伴奏版本。

目前是本地Python/CPU实现，未迁移进Android。手机原先的40秒识别/上传和512事件限制还在。桌面整曲结果不等于手机整曲上传已支持。所有confidence=0只表示没有可用的校准置信度。

## 开源依据和验证

- [ROSVOT / RWBD](https://github.com/RickyL-2000/ROSVOT)：官方模型和代码，MIT；只用声学字界时不能声称识别出了具体汉字。
- [GAME ONNX](https://github.com/openvpi/GAME/blob/main/ONNX.md)：官方1.0.3 medium、8步、0.2边界与存在阈值，MIT。
- [FCPE](https://github.com/CNChTu/FCPE)：官方torchfcpe 0.0.4包内模型实际推断，MIT。它是音高估计器，本轮没有使用其简单f0量化MIDI替代分段。
- [SOFA](https://github.com/qiuqiao/SOFA)：仅调研，依赖文本/音素，本轮未执行，不能算已接入歌词识别。

10项行为测试覆盖颤音不碎分、同音重复字、140ms真实短音、40ms真实休止、跟踪丢失、真实八度、罕见半音、移调、无声误检和物理谐波证据。它们验证程序行为，不代表曲目听感合格。所有导出MP3探测、MIDI毫秒回读、缓存复用、59个Android生产文件哈希核对结果在validation.json。源代码与模型哈希在source和provenance.json，模型权重没有打包。
'''
    (O/'本轮改动与试听说明.md').write_text(report,encoding='utf8')
    manifest={str(p.relative_to(O)).replace('\\','/'):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='sha256.json'}
    (O/'sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    archive=Path(shutil.make_archive(str(O),'zip',root_dir=O.parent,base_dir=O.name))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf8')
    print('saved',O,'archive bytes',archive.stat().st_size,'files',len(manifest)+1,flush=True)

if __name__=='__main__':main()
