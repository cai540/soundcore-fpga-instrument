# 人声主音识别核心：实验版本

此包是正在验证的新核心，尚未通过产品验收，没有集成到 APK 或 FPGA 固件。当前没有达到一首完整人声99%、另两首95%的证据；局部片段的较好数字不能代替整曲结果。

## 固定原始观测＋自动歌声字界（本轮候选）

新增 `vocal_units.py`，职责限定为三个数值步骤：按自动元音范围池化固定原始 GAME 观测；从两路基频相互支持的音级估计软调性分布；复用 `articulation.py` 的同一序列分类器选择主音。`pitch.py` 只提供源基频与已验证的颤音中心测量。没有对音符输出执行移调、删音、补音或曲名分支。软调性保留全部十二种音阶旋转，最低似然为0.1，强声学证据仍可保留真实半音；音级一致不能强制改变八度。

本轮三段固定40秒都使用相同配置。按重新审计原简谱后的逐字简化标准，祖国49/50、牵丝戏61/61、敕勒歌50/50；后两首的音高序列与此前认可版本完全一致，重新估计了字的起止与休止。祖国仍有“一首赞歌”的“一”低一八度。每个自动发音单位仅保留一个主音，不等于逐个还原原谱全部转音。

校对表有独立修改记录：原简谱“无论我走到哪里”的“我”是6，“走”包含5→4，旧表曾将这些音归错字。旧表与旧结果保留在原处；按同一审计后标准，旧版祖国45/50、新版49/50；机械沿用旧表时新版47/50。此修订不算算法改进。参数使用过这些开发片段，不能宣称这是未知歌曲准确率或整曲验收；实际逐字时值尚无独立金标准，听感未验收。

上游自动文本来自 Qwen3-ASR，歌声对齐使用 [TIFA](https://github.com/openvpi/TIFA)。观察器仍在本地研究环境，未接入手机；FCPE 的 DDSP 模型仅用于本地研究，未打包进 App。VocalParse、强制短时窗、输出修补与多轮分音阈值试验未用于最终候选。

试听、源时间轴MIDI、审计前后校对表和独立复算源码：`D:\FPGA\Projects\soundcore_2026\output\vocal_units40_20261030\试听与核对.html`。只复算数值决策时不需要大模型，也不导入研究或评价代码：

```powershell
python -m tools.decode_vocal_units `
  --evidence output/vocal_units40_20261030/zuguo/source_unit_evidence.npz `
  --config output/vocal_units40_20261030/config.json `
  --output build/vocal_unit_replay
```

`tools/pack_vocal_unit_cache.py` 可由指定源音频与观察器结果生成缓存，并检查原始44.1k、对齐48k和第二基频16k输入的哈希。录音字界、音高分布、基频测量均保留源时间轴和文件指纹，缓存不是先前修改好的MIDI答案。

## 逐字主音候选（2026-10-30）

新增 `articulation.py`，把一个自动识别发音单位的音符数量直接限制在图内：默认一个主音，显式设置时最多两个。相邻的同音字仍各自保留敲击，80 ms 的真实短字不会因为转音片段的最小时长限制而消失；句间实际休止保留。没有对已输出音符做删音、移调或合并修补。

此模块分为两个明确步骤：分配每个发音单位的原始时间范围，然后对其有界主音序列做音高分类。候选区间共用固定的原始观测；不会每换一个切法就重新询问模型。主音采用时间加权混合，相比几何交集能保留多个候选，但较宽的模型音高分布重叠时仍会选错中间音，尚未彻底解决。

自动识字及字界观察器仍处于研究阶段，尚不能保证实际每个歌词字都被正确定位。40秒候选实际输出50/61/50个单音单位，祖国44/50、牵丝戏61/61、敕勒歌50/50符合独立谱面允许的逐字简化主音。数字包含八度并核对每字归属，不允许拿前一字多出的转音抵消后一字漏音。这只是三个开发片段的主音核对；没有测逐字起止、节奏准确率或完成听感验收。99/95/95门槛仍未通过，旧入口的完整人声基线未被替换。

字界对齐失败不能把零时长字补宽成音符。新增观察器的失败实验保存在 `build/`，包括Qwen时间模型、普通话CTC对齐和HuBERT内容边界；它们没有作为多层结果修补追加到正式解码中。没有把歌曲标题、正确歌词、简谱或手工修改MIDI提供给运行时。ASR仍有同音误识字，输出中的识别文本不应当作已校对歌词。

候选试听与报告：`D:\FPGA\Projects\soundcore_2026\output\vocal_carriers40_20261030\试听与核对.html`。从固定声学证据单独复算，不导入研究脚本或谱面：

```powershell
python -m tools.decode_vocal_carriers `
  --evidence output/vocal_carriers40_20261030/qiansixi/articulation_evidence.npz `
  --config output/vocal_carriers40_20261030/config.json `
  --output build/carrier_replay
```

`ArticulationEvidence`是带版本的自动声学缓存，记录原始音频哈希和观察器来源；这条复算命令不意味着手机已经接入大模型识字或新的字级算法。

已认可音高、只继续调整时值时，可以给上述命令增加 `--lock-pitch-input`，指向同一段录音先前生成的 `characters.json`。入口同时检查录音哈希及发音单位的顺序；不允许把别的录音或不同字序的音高套入当前时间轴。`align_carrier_timing` 使用同一时间图估计起止，每个单位已确认的一至两个音高及其顺序保持不变，相邻同音字和真实休止仍保留。此模式不重新估计音高，输出明确记录父文件指纹。它是继续校对节奏的工具，不意味着新的时值已经听审通过。

## 一个入口、一套决策

运行入口是 `python -m soundcore_audio`。运行时只接收录音、模型和一份显式参数配置；不读取歌曲名字、简谱、人工修订 MIDI、歌词或评价目录。参数文件必须显式指定，避免把未验收的默认设置当成正式版本。

数据依次经过以下模块：

| 文件 | 责任 |
|---|---|
| `audio.py` | 带限重采样、原始时间轴、带足够上下文的录音分段 |
| `game.py` | 原始 GAME 编码和边界、音高激活；内容缓存 |
| `features.py` | 原始 RWBD 发音边界；保留已与 App 数值对照的频谱测量 |
| `pitch.py` | 原始 RMVPE 基频；复用经过验证的颤音中心测量 |
| `types.py` | 只读观测、音符和单一目标函数的参数 |
| `decoder.py` | 固定观测下的候选区间和一次动态规划，联合选择分界、主音、休止 |
| `pipeline.py` | 组织观测、证据格式验证、MIDI 原始毫秒时钟导出 |
| `__main__.py` | 参数、结果和可复查的来源记录 |

不会在输出上依次运行“改八度、改主音、删短音、合并同音、再补音”的规则链。分音和主音的冲突在同一个目标函数里比较。颤音中心只提供音级证据，不强迫改变八度。时值使用录音自身的中位时长作软约束，没有硬删短音。

候选区间共用原始模型观测，不为每一种切法反复改变模型上下文。旧研究脚本保留作比较，不被此包导入。没有因为文件重命名而改变处理的逻辑。

同一候选区间分别保留原始音高似然和独立池化的有声概率，避免把音高分歧当作静音。这个数学修复已完成结构检查，但没有显著提高目前四份整曲输出的谱面匹配率，不宣称解决了八度或碎音问题。新增音节、半周期和其他基频模型的尝试仍在build研究目录，未追加为运行时修补链。

## 重现运行

依赖由根目录 `pyproject.toml` 声明，另需系统 `ffmpeg`。模型导出工具位于 `tools/`，仅导出原始权重和前端，不参与运行时推理。当前本机可用环境示例：

```powershell
Set-Location D:\FPGA\Projects\soundcore_2026
$env:PYTHONPATH=(Resolve-Path build/vocal_decoder_refactor_20261030/tools).Path+';'+(Resolve-Path build/vocal_oss_20261029/extra).Path+';'+(Get-Location).Path
& build/vocal_oss_20261029/venv/Scripts/python.exe -m soundcore_audio input.wav `
  --models build/vocal_oss_20261029/game_models/medium/GAME-1.0.3-medium-onnx `
  --words .audio_models/word_boundary --pitch .audio_models/pitch `
  --cache .audio_models/cache `
  --config evaluation/transcription/candidate_20261030.json --output output/transcription_candidate
```

正常输出包括 `notes.csv`、`source_clock.mid`、`observations.npz`、`audit.json`、`manifest.json`。缓存保存模型观测，不保存按歌名查找的答案。观测格式包含策略版本和模型指纹，旧的、无标签的实验缓存会被拒绝，不默默沿用。

## 测试边界

运行 `python -m unittest discover -s tests -v`。测试覆盖真实短音、同音重复发音、真实八度跳进、长音、休止、原始观测不被覆盖、旧缓存拒绝、MIDI 毫秒时钟和运行时隔离。测试通过不等于歌曲音准达标。

独立谱面校对、参数拟合、误差统计放在 `evaluation/transcription/`，与运行时分开。当前验收结果与局限见该目录的 `README.md`。
