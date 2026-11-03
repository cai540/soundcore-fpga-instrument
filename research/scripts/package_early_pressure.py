"""Archive the exact candidate and reusable profile, with honest evidence labels."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/early_pressure_20261028'
OUT=ROOT/'output/early_pressure_20261028';OUT.mkdir(parents=True,exist_ok=True)
r=json.loads((BUILD/'release.json').read_text(encoding='utf-8'))
assert not r['sram_written'] and not r['flash_written']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(Path(r['firmware']))==r['sha256']
for name,h in r['source_sha256'].items():assert sha(ROOT/name)==h,name
readme=f'''# 声芯：保存力度参数与提前发声实验版

2026-10-28 · 固件{r['user_code']} · 配置ID {r['saved_profile']['profile_id']} · 完整耳机工程 · **未烧录**

## 这次解决了什么

已经把之前接受过的力度曲线保存成固定配置，程序直接使用，不需要每次开机重新试轻按、重按或输入参数。正常开机仍会自动读取每片16次空载值作为零点，整个过程由程序完成。开机时保持传感片放松即可。

配置常数随新固件加载。以后将此版写入开发板已有的配置Flash，断电重启仍会使用这套配置；只写SRAM则是临时运行，断电后恢复Flash中的原版。本次既未写SRAM，也未写Flash。

以后更换传感片、电阻分压、机械安装方式时，才可能需要更新一次配置。更新后的版本同样能持续复用。这里保存的是已有静态调试结果；没有把虚构的敲击数据当作训练结果。

## 提前发声怎样工作

原版：超过触发门限后，再等4次该传感片的采样，取这段时间内的最大值发声。

实验版：如果连续两次读数在门限以上并且不再上升，峰值也留有足够余量，就先发声；如果判断条件不足，继续按原来的时间等待。后面发现更大的力度时，只平滑提高当前声音的力度，不再多发一次音。

32个独立声部、35个可选音高及已完成的共享音高计算保留。七片都能使用此路径。旧的音量补偿也保留；新增的逐片增益暂时全部为1，因为没有可靠的七片动态标定数据。

**这是一版保守的早期判断规则，还没有用真实敲击波形训练预测模型。** 合成测试可以证明逻辑行为，不能证明实际手感、音准改善或传感到声音已小于5ms。

## 已验证

- 原力度曲线4096种输入逐点一致，七片共28672个映射检查通过；关闭实验时与冻结的原检测器逐周期一致。
- 48组人工合成场景检查：稳定/衰减波形提前，慢上升、低余量、短尖峰按原版回退；七片和弦、释放、零点采样和不重复发音通过。
- 2928条保存、重载的合成采样在离线工具和RTL中逐条一致；CSV异常值、时间戳重复/倒退会被拒绝，计数器回绕可识别。
- 七个声部从临时力度30提高到最终212时保持原声部，不补发起音；释放其中一片不影响其他六片。
- 新旧开关状态下的完整ADC到耳机音频路径通过，实体与手机声部独立检查通过。合计10项RTL检查通过，另有CSV校验。
- 公开引脚及37项保护文件未变化；APK、歌曲和接线文件未改。

## 完整芯片构建结果

| 项目 | 使用量 | 相对共享音高版 |
|---|---:|---:|
| Logic | {int(r['resources']['Logic']['used'])}/59904 | +230 |
| 寄存器 | {int(r['resources']['Register']['used'])}/60780 | +201 |
| BSRAM | 45/118 | 不变 |
| DSP | 45.5/118 | 不变 |

Setup余量+{r['setup_slack_ns']}ns，Hold余量+{r['hold_slack_ns']}ns，均无违例。通过布局布线不代表已完成实物测试。

## 保存的东西在哪里

- `config/pressure_profile_v1.json`：原静态调试依据、固定曲线、逐片增益和实验判据。
- `firmware/`：本次完整耳机实验位流。
- `sources/`：与位流哈希对应的工程源码和配置快照；包含原工程的绝对路径引用，复建仍需项目原环境。
- `tools/`：配置生成、保存CSV回放、检查、构建和归档脚本。
- `evidence/`：检查结果、资源、时序及引脚报告、发布清单。
- `synthetic_data/`：六种人工生成的测试波形与回放结果，**不是真实传感片测量**。
- `capture_foundation/`：带时间戳的原始波形环形缓存模块及测试；尚未接入主工程或蓝牙导出，因此没有包含在本次产品位流中。

后续真实波形可长期保存为CSV，字段为clock、channel、adc，可选trigger。回放应包含每片至少16次开机空载观测，或使用与该次采样匹配的初始零点文件。不能把裁剪后的短片段直接当成完整启动序列。

## 工程中的复现顺序

在原项目根目录依次运行：

```text
python scripts/generate_pressure_profile.py
python scripts/check_pressure_replay.py
python scripts/check_early_pressure.py
python scripts/prepare_early_pressure_build.py
gw_sh.exe build/early_pressure_20261028/gowin/build.tcl
python scripts/finalize_early_pressure.py
```

这组命令不会烧录。脚本保留原0xC2B3和0x9D67位流；已发布的实验位流也不允许被不同内容静默覆盖。
'''
(OUT/'说明_固定参数与提前发声实验.md').write_text(readme,encoding='utf-8')
def copy(p,relative):
    p=Path(p);dest=OUT/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
copy(Path(r['firmware']),Path('firmware')/Path(r['firmware']).name)
for name in r['source_sha256']:copy(ROOT/name,Path('sources')/name)
copy(ROOT/'config/pressure_profile_v1.json','config/pressure_profile_v1.json')
for name in ['release.json','tests.json','profile_manifest.json','resource_report.txt','timing_report.html','pin_report.html','gowin_build.log','saved_curve.mem','build_input_sha256.json']:
    copy(BUILD/name,Path('evidence')/name)
for p in (BUILD/'replay').iterdir():
    if p.is_file():copy(p,Path('synthetic_data')/p.name)
for name in ['prepare_early_pressure_state.py','generate_pressure_profile.py','replay_pressure_trace.py',
    'check_pressure_replay.py','check_early_pressure.py','prepare_early_pressure_build.py',
    'finalize_early_pressure.py','package_early_pressure.py','check_organic_build.py']:
    copy(ROOT/'scripts'/name,Path('tools')/name)
for p in ROOT.joinpath('tb').glob('*pressure*.v'):copy(p,Path('tests')/p.name)
copy(ROOT/'tb/tb_fsr_trace_capture.v','capture_foundation/tb_fsr_trace_capture.v')
copy(ROOT/'rtl/fsr_trace_capture.v','capture_foundation/fsr_trace_capture.v')
for name in ['tb_panel_audio_integration.v','tb_realtime_voice_integration.v']:
    copy(ROOT/'tb'/name,Path('tests')/name)
for p in (BUILD/'baseline').rglob('*'):
    if p.is_file():copy(p,Path('baseline')/p.relative_to(BUILD/'baseline'))
for name in ['docs/plans/2026-10-28-persistent-early-pressure.md','docs/innovation_roadmap_2026-10-28.md']:
    copy(ROOT/name,Path('docs')/Path(name).name)
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json']
manifest={p.relative_to(OUT).as_posix():sha(p) for p in files}
(OUT/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT/'固定参数与提前发声实验_20261028.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files+[OUT/'SHA256.json']:z.write(p,p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h,name
print(json.dumps({'archive':str(archive),'files':len(manifest),'bytes':archive.stat().st_size,
    'readme':str(OUT/'说明_固定参数与提前发声实验.md')},ensure_ascii=False,indent=2))
