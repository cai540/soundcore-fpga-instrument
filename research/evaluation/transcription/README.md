# 2026-10-30 校对结果与验收边界

**状态：未通过整体验收，更未达到新要求的一首99%、另两首95%。** 参数只在开发片段拟合，随后冻结。四首曲目均有独立谱面片段校对；没有使用旧的人工编辑程序输出作为音高答案。

## 新增整段核对与当前门槛

`zuguo_complete_score.json`从所给简谱重读28行、215个主音，旧歌词文件只提供粗定位，不提供音高。核对范围为原录音47.0–205.8秒；范围内句间多余音仍计错，不能靠删除难识别的人声段提高比例。谱面与实际演唱可能存在变体，当前标注不是独立逐音听写或毫秒节奏金标准。

当前核心对该完整范围匹配179个主音，20个错音、16个漏音、14个多余音。精确率84.04%、召回率83.26%；把三类错误都计入后，严格主音顺序一致性为**76.74%**。这不是对任意录音的准确率估计，也不是节奏准确率。

新门槛由`metrics.song_pitch_gate`检查：三首不同、完整标注的人声歌曲，严格一致性分别至少99%、95%、95%。只标了几句的片段和同一歌曲的两个片段不能充作三首。当前只有一首完整谱面标注，且未过线，整体验收结果为false。

本轮消融未并入运行时：

| 对照 | 可复查结果 | 决定 |
|---|---|---|
| 无文本SOFA音节强制分音 | 牵丝戏开头32/34，祖国开头漏18个 | 不采用；不能以一个字一音为由删正常音 |
| FCPE DDSP直接替换基频证据 | 牵丝戏开发34/34且无多余音，但祖国完整核对变差 | 不采用，不把片段100%当整曲99% |
| SOFA音节软边界、人声/停顿证据 | 未明显消除整曲的句尾多余音，强制边界还会新增碎音 | 不采用 |
| 保留多峰的训练核反卷积调性 | 开发祖国由48/53降到47/53 | 不采用 |
| 原声半周期重复支持的向上八度备选 | 祖国完整核对最多181/215，仍18错、16漏、14多余 | 仅研究，未达验收且没有独立泛化证据 |
| 两种基频中心证据融合 | 祖国开发多匹配1音、整段少1个多余音，改善不足 | 仅研究，未替换核心 |

完整原始报告保存在`build/sofa_20261030/`和`build/fcpe_20261030/`。推理不读取这些标注，也没有根据曲名选择模型、按时间改音或用旧成品谱作答案。

## 历史固定参数的短片段结果

| 校对片段 | 谱面主音数 | 正确匹配 | 预测主音精确率 | 主音召回率 |
|---|---:|---:|---:|---:|
| 我和我的祖国：开发段 | 53 | 48 | 94.12% | 90.57% |
| 牵丝戏：开发段 | 34 | 33 | 97.06% | 97.06% |
| 敕勒歌：扩展回归段 | 15 | 15 | 93.75% | 100.00% |
| 我和我的祖国：后段 | 45 | 41 | 91.11% | 91.11% |
| 兰亭序：新加入的两句 | 23 | 21 | **80.77%** | 91.30% |

开发段以外的 83 个谱面主音，正确匹配 77 个，预测 87 个：精确率 88.51%，召回率 92.77%。因此不能用开发段达标，或合并开发样本后的数字，声称整个通用功能达到 90%。

《兰亭序》仍有 2 个主音偏差和 3 个多余音符，是当前明确未通过的项目。前三首也只是所列片段达到音高匹配门槛，不代表整曲已经通过听感、逐字起止、停顿和节奏验收。

## 指标的含义

- 精确率 = 正确匹配 / 预测音符数，惩罚额外音和错音。
- 召回率 = 正确匹配 / 谱面主音数，惩罚漏音和错音。
- 以句内顺序匹配音高，八度必须正确，没有把 ±1 半音视为正确。
- 句子外框仅作定位，按重叠时长归属且不重复计数。它不是逐音毫秒标注，不用于宣称节奏准确率。
- 乐谱中的延音线不算新的发音；明确的同音重复字保留。谱面来源和录音八度核对记在各数据文件的 provenance 中。

开发段 87 音用于拟合，不能再当成未见测试。最初的 60 音扩展验证后来已被查看，应视为扩展回归。新加入的《兰亭序》在参数冻结后才测试，结果未过线；后续若依其错误继续调整，须另外保留新的独立验证材料。

## 可重现命令

在项目目录、配置好 Python 依赖后运行：

```powershell
python -m evaluation.transcription.evaluate --labels evaluation/transcription/zuguo_complete_score.json --observations build/vocal_register_clean_20261030/presence_evidence --config evaluation/transcription/candidate_20261030.json --output build/transcription_complete_replay
python -m evaluation.transcription.evaluate --labels evaluation/transcription/development.json --observations build/vocal_register_clean_20261030/presence_clip_evidence --config evaluation/transcription/candidate_20261030.json --output build/transcription_development_replay
python -m evaluation.transcription.evaluate --labels evaluation/transcription/lantingxu_unseen.json --observations build/vocal_register_clean_20261030/presence_clip_evidence --config evaluation/transcription/candidate_20261030.json --output build/transcription_unseen_replay
```

`evaluate` 不会调参。报告包含配置、标签和代码哈希。旧实验结果位于 `build/vocal_decoder_refactor_20261030/`，包括失败的频谱单独分界、大模型替换、不同上下文、强制字边界和直接替换 F0 的消融。失败方案没有作为新的输出修补层接进运行时。

当前证据策略为`native-30-45s-fixed-log-pool-separate-voicing-v2`，分别记录音高似然与有声概率。原始v1缓存不能直接交给当前加载器；`migrate_presence_evidence.py`只对冻结的旧观测做显式转换，保留原数组并核验音高池化逐值不变，另存来源与目标哈希。新输入通过当前CLI重新准备。序列化不允许混合有/无基频证据，长度不一致也会报错，不能由zip静默漏掉尾部区间。
