"""Package the verified expression candidate and its reproducible evidence."""
from pathlib import Path
import hashlib, json, shutil, zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/expression_20261028'
OUT = ROOT/'output/expression_20261028'
OUT.mkdir(parents=True, exist_ok=True)
r = json.loads((BUILD/'release.json').read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert not r['sram_written'] and not r['flash_written']
assert sha(Path(r['firmware'])) == r['sha256']
for name, digest in r['source_sha256'].items():
    assert sha(ROOT/name) == digest, name
for name, digest in r['evidence_sha256'].items():
    assert sha(BUILD/name) == digest, name

def copy(p, relative):
    destination = OUT/relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, destination)

rows = []
for name, x in r['resources'].items():
    rows.append(f"| {name} | {x['used']:g}/{x['total']} | {x['utilization_percent']:.2f}% | {x['delta_from_early_pressure']:+g} |")
measurements = {x['timbre']: x for x in r['spectral_validation']['measurements']}
h, e = measurements['harmonica'], measurements['erhu']
readme = f'''# 声芯：持续按压表情与受控音色实验版

2026-10-28 · 固件 {r['user_code']} · 完整耳机工程 · **未烧录**

## 现在能做什么

敲下时保留原来的起音力度；按住同一个音以后，可以继续加压，再减轻压力。声音的力度与谐波配比会平滑变化，七片各自控制自己的声音。原版只会跟进更大的峰值，这版增加了长音阶段可增、可减的持续控制。

起音力度先保持40ms，再接入持续压力；这40ms不是等待40ms才发声。原有提前判断、柔和起音、颤音和释放尾音保留。新控制含死区和有界平滑，轻微抖动不会直接变成突然的音量变化；其真实手感仍需实板评价。

口琴与二胡分别使用六项算法谐波和很轻的气流/弓擦成分，随音高和表情改变参数。改变谐波比例时另作能量补偿，避免音色变亮附带大幅增音。正常加压带来的力度变化仍然保留。没有采用乐器录音采样，也没有宣称完成真实口琴或二胡的物理模型。

## 参数会一直保留

力度配置ID `{r['saved_pressure_profile']['profile_id']}`、表情配置ID `{r['saved_expression_profile']['profile_id']}` 已保存。正常启动直接复用，不需要重新试音或反复标定。原有开机16次空载零点采样仍自动完成。

这些常数编译在位流中。以后写入Flash，正常断电重启仍会使用；仅写SRAM则随断电失效。本次两种存储都没有写入。参数来源是既有力度曲线与人工设计的音色参数，没有虚构实测训练数据。

## 怎么听

- `audio/harmonica_old_then_new.mp3`、`erhu_old_then_new.mp3`：前6秒旧版，静音0.5秒，后6秒新版；同一公共增益。每段含持续增减压和一段短旋律。
- `audio/harmonica_new.mp3`、`erhu_new.mp3`：单独听新版。
- `audio/*_four_ablations.mp3`：依次为旧版、仅持续控制、新音色不补偿、新音色加补偿，各6秒，段间0.25秒。
- `audio/*_RMS_matched_AB.mp3`：另行标注的RMS匹配对照，便于减少音量差带来的判断偏差；它与统一增益对照的用途不同。

试听来自真实RTL运行输出，采用与产品相同的新音色及包络内核；是单声部数字预览，**不是板载耳机/音响录音，也不是整曲试听**。声音是否更像真实乐器，需要实际听感判断。

## 检查结果

- 12项RTL检查通过。关闭新功能时，1400帧PCM与冻结的1C8A逐位一致。
- 32独立声部、48kHz、每采样帧256个时钟保留；新路径225拍完成，余31拍。225拍约18.31微秒，这是数字计算时间，不能代替按压到模拟出声的实测延迟。
- 700帧满32声部排程，5580次不相关声部贡献比较，均通过。一个声部的表情变化不串到其他声部。
- 双读ROM替代大组合表；17920个音高/音色/表情组合与原组合表逐位一致，覆盖32份独立随机纹理状态。
- 实际RTL检查两种音色、35音高、9个表情位置，共630组；固定演奏幅度下，口琴额外RMS跨度约{h['normalized_span_db']:.3f}dB，二胡约{e['normalized_span_db']:.3f}dB。未补偿分别约{h['uncompensated_span_db']:.3f}dB和{e['uncompensated_span_db']:.3f}dB。
- 全部17920个插值位置的数值参考跨度约{r['spectral_validation']['all_reference_interpolation_span_db']:.3f}dB。RMS是电平指标，**不是主观等响或乐器逼真度证明**。
- 音色源扫描及上述试听没有削顶；不据此宣称任意32个满幅、同相声部同时混音永不饱和，原总混音限幅仍在。
- 七片持续减压、加压、峰值修正不重触发、释放尾音、手机与实体归属、实际ADC到PT8211耳机数字输出检查通过。
- 公开引脚和{r['protected_files_unchanged']}项保护文件一致。App、歌词、两首歌曲、接线分配保持原样。

## 完整布局布线

| 资源 | 用量 | 占比 | 相比1C8A |
|---|---:|---:|---:|
{chr(10).join(rows)}

Setup余量+{r['setup_slack_ns']:.3f}ns，Hold余量+{r['hold_slack_ns']:.3f}ns，零违例。仍需实板确认手感、实际听感和端到端延迟。

## 使用范围

实体压力片：起音峰值与持续表情分开，按住后可连续增减。

手机演奏：保留现有按下/松开和初始力度协议，初始力度也决定新音色的表情；本次没有新增手机持续压力协议。

脱机歌曲：使用新音色源及指定固定表情176，音符、歌词、曲速和进度逻辑未改。选中此实验顶层才启用新路径；普通顶层默认关闭，保留回退。

## 文件与复现

`firmware/`是本次独立候选；`sources/`是位流输入快照；`config/`是可复用配置；`evidence/`含发布清单、630组测量、日志和芯片报告；`tests/`、`tools/`及`baseline/`用于对照复现。两份`.mem`存六个谐波系数，不存PCM音频。

在原项目环境按顺序运行：

```text
python scripts/generate_expression_profile.py
python scripts/check_expression.py
python scripts/audition_expression.py
python scripts/validate_expression_audio.py
python scripts/analyze_expression.py
python scripts/prepare_expression_build.py
gw_sh.exe build/expression_20261028/gowin_rom/build.tcl
python scripts/finalize_expression.py
python scripts/package_expression.py
```

这些步骤不会扫描或烧录硬件。冻结基线已经包含在包中，**不要在修改后的源码上重新生成基线**。工程含原机器绝对路径，迁移时需统一修改工具位置、工程路径和ROM文件路径，再完整复验；此包不宣称在任意电脑解压即编译。

## 竞赛中怎样表述

可以表述为：面向32复音乐器，将起音峰值与持续压力解耦，设计独立的逐声部表情平滑、随音高/表情变化的定点音色参数与能量补偿，并在225/256拍的约束内实现；通过消融、数值对照及资源时序给出证据。

这属于本项目具体架构和实现的技术改进。压力控制音色、谐波合成、能量归一化以及分时处理都有先行工作，不能把这些基本原理称为学术首创。当前状态是“仿真与布局布线验证完成、实板待验”。
'''
(OUT/'说明_持续表情与受控音色.md').write_text(readme, encoding='utf-8')
copy(Path(r['firmware']), Path('firmware')/Path(r['firmware']).name)
for name in r['source_sha256']:
    copy(ROOT/name, Path('sources')/name)
for name in ['pressure_profile_v1.json', 'expression_profile_v1.json']:
    copy(ROOT/'config'/name, Path('config')/name)
for path in r['audition']['preview_files'].values():
    copy(Path(path), Path('audio')/Path(path).name)
    copy(Path(path).with_suffix('.wav'), Path('audio')/Path(path).with_suffix('.wav').name)
for name in list(r['evidence_sha256'])+['release.json', 'build_input_sha256.json', 'expression_response.png']:
    copy(BUILD/name, Path('evidence')/name)
for name in ['prepare_expression_state.py', 'generate_expression_profile.py', 'check_expression.py',
             'audition_expression.py', 'validate_expression_audio.py', 'analyze_expression.py', 'prepare_expression_build.py',
             'finalize_expression.py', 'package_expression.py', 'check_organic_build.py']:
    copy(ROOT/'scripts'/name, Path('tools')/name)
for item in r['tests']:
    copy(ROOT/'tb'/(item['test']+'.v'), Path('tests')/(item['test']+'.v'))
copy(ROOT/'tb/tb_expression_audition.v', 'tests/tb_expression_audition.v')
copy(BUILD/'lut_lookup_trial/lut_expression_texture.v', 'reference/lut_expression_texture.v')
for p in (BUILD/'baseline').rglob('*'):
    if p.is_file():
        copy(p, Path('baseline')/p.relative_to(BUILD/'baseline'))
for name in ['docs/plans/2026-10-28-continuous-expression-implementation.md',
             'docs/innovation_candidates_2026-10-28.md', 'docs/innovation_roadmap_2026-10-28.md',
             'docs/expression_review_2026-10-28.md']:
    copy(ROOT/name, Path('docs')/Path(name).name)
files = [p for p in OUT.rglob('*') if p.is_file() and p.suffix != '.zip' and p.name != 'SHA256.json']
manifest = {p.relative_to(OUT).as_posix(): sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
archive = OUT/'持续表情与受控音色实验_20261028.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files+[OUT/'SHA256.json']:
        z.write(p, p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name, digest in manifest.items():
        assert hashlib.sha256(z.read(name)).hexdigest() == digest, name
print(json.dumps(dict(archive=str(archive), files=len(manifest), bytes=archive.stat().st_size,
                     readme=str(OUT/'说明_持续表情与受控音色.md')), ensure_ascii=False, indent=2))
