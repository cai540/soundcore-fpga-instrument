from pathlib import Path
import json,re,zipfile,os,subprocess
R=Path(__file__).resolve().parents[1];B=R/'build/low_latency_20261101';O=R/'output/low_latency_20261101'
m=json.loads((O/'release.json').read_text(encoding='utf8'));c=m['comparison'];p=B/'portable_check';p.mkdir(exist_ok=True)
with zipfile.ZipFile(O/'低延迟_完整FPGA工程.zip')as z:z.extractall(p)
refs=0
for f in (p/'src').rglob('*'):
    if f.suffix not in ['.v','.vh']:continue
    body=f.read_text(encoding='utf8');assert 'D:/FPGA/'not in body,f
    for name in re.findall(r'"(src/[^"\n]+)"',body):
        assert (p/name).is_file(),(f,name);refs+=1
files=list((p/'src').rglob('*.v'))
os.environ.update(TEMP=str(R/'tmp'),TMP=str(R/'tmp'))
check=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012','-E','-o',str(B/'portable_preprocessed.v'),*map(str,files)],cwd=p,capture_output=True,text=True)
assert check.returncode==0,check.stderr
(O/'evidence/portable_source_check.json').write_text(json.dumps({'verilog_sources':len(files),'relative_references':refs,
    'all_relative_assets_present':True,'preprocessor_passed':True,'vendor_full_build':'separately passed synthesis and PNR'},indent=2),encoding='utf8')
text=f'''# 低延迟候选版（2026-11-01）

固件 UserCode **{m['user_code']}**，APK **0.17 / versionCode 17**。在七自然音候选7B69基础上优化。没有烧录SRAM或Flash，接线不变。

## 实体敲击：数字链路已经变快

测量起点是ADC输入电压模型从1000跃变到2200；特意错过当前通道采样孔径。终点来自实际I2S输出左声道16位字，固定音量16/31、音效关闭。全部仍经过正式扫描器、早触发、力度控制、声部分配、32声部合成与I2S发送器。

| 相同测试条件 | 上一候选7B69 | 本候选 |
|---|---:|---:|
| 原16组最慢达到PCM绝对值64 | {c['old_max_abs64_ms']:.3f}ms | {c['new_max_abs64_ms']:.3f}ms |
| 强制完整峰值窗口，两种音色C4最慢达到64 | {c['old_forced_fallback_max_abs64_ms']:.3f}ms | {c['new_forced_fallback_max_abs64_ms']:.3f}ms |

新增覆盖C调五音区×七键×两音色，共70组：最慢首个非零I2S字 **{m['latency']['max_step_to_first_nonzero_i2s_ms']:.3f}ms**，最慢达到绝对值64 **{m['latency']['max_step_to_abs64_i2s_ms']:.3f}ms**。将全部70组再强制改为等待完整峰值窗口时，最慢达到64为 **{m['fallback_all_octaves']['max_step_to_abs64_i2s_ms']:.3f}ms**。不是对全部移调、任意力度和任意模拟负载的保证。

PCM阈值64/32768约为-54dBFS，是固定对比判据，不等同于“人耳能听见”“达到50%振幅”或整机起音延迟。模型不包含传感片机械响应、真实ADC源阻抗与采样建立、MAX98357A内部数字/模拟延迟、扬声器和空气传播。最终竞赛＜5ms仍需实测。

## 起音与音色

- 口琴缓起从256采样缩为128采样，即5.333ms→2.667ms；二胡从512缩为256，即10.667ms→5.333ms。50%包络分别约1.333ms、2.667ms，从合成器收到音符算起，不是从手指接触算起。
- 保留二次S曲线的零起始/终止斜率、无音量过冲、重复触发时保留原包络和相位、原释放规则。实时和脱机引擎共用一份函数，避免两处时常不一致。
- 没有更换持续音色、气声/噪声参数、颤音、音效、传感片阈值或力度校准。比较实际RTL的4560帧：两音色、C2/C4/C6、力度72/220、实时/脱机两引擎，起音结束后的持续和释放PCM与7B69逐位一致。起音的真实听感仍待上板确认。

## 手机蓝牙：优化发送和拥塞

- 使用统一串口带宽预算处理演奏、设置和重试。9600波特率下，七键快照9字节本身需9.375ms，完整半音快照16字节需16.667ms。新调度按实际字节数向上取整，再预留2ms，并从GATT回调时保守计时。
- 原来统一16ms的键盘间隔被取消。回调很快时，七键快照预算为12ms；完整半音快照为19ms，避免按16ms连续发送却超过串口吞吐。
- 完整半音键盘的最终松手使用兼容的零持音短快照，从16字节缩到9字节；不会把半音误映射为自然音，零持音后下一次按下仍发送准确半音。固件端已验证可清除全部七个持音及未发出的起音。
- 按下/松开使用“当前手指状态”邮箱，传输忙时覆盖过期状态。未发出的、已松开的极短点击会被取消，不在收手后排队补奏。无线条件很差或点击快于链路吞吐时，无法保证每个极短音都被送到。
- 弹奏中延后周期性力度、状态、音区和识别进度查询；松开后安静120ms再恢复。指引按键触发的下一目标查询仍然优先保留，即使已有旧查询正在等待回复，也会合并成一条新的查询。
- 保留当前持音快照的500ms续租；该快照本身刷新FPGA会话，无需再发送重复心跳。零持音时照常保活。显式设置和停止指令不会被当成后台查询延后。
- 演奏页申请较高蓝牙连接优先级，离开后恢复均衡；系统及模块是否接受取决于设备。[Android官方接口](https://developer.android.com/reference/android/bluetooth/BluetoothGatt#requestConnectionPriority(int))
- 串口仍为9600，没有发送AT配置指令。一个GATT写入未回调时不启动第二个；超过1秒仍无回调则断开会话，避免迟到回调误认成后续帧。FPGA持音还有1.5秒租约保护。

以上是调度实现与确定性测试结果，没有测手机到声音的真实延迟，也不承诺蓝牙＜5ms。BLE无线缓冲、系统调度及串口转发仍会增加时间。

## 兼容与完成检查

七自然音、五音区、12调、完整半音、32声部、五键、灯环、OLED、音效、两首内置曲和双识别离线模型均保留。音响外放版，物理CST与7B69/EAE0逐字节一致。没有加入API、服务端或INTERNET权限，0.17与上一APK同签名，可覆盖安装。

- {m['rtl_checks']}项RTL检查通过；另外完成70组正常延迟、70组强制完整窗口、2组C4旧版对照条件，以及4560帧PCM对照。
- Android {m['android']['tests']-m['android']['skipped']}项通过，{m['android']['skipped']}项跳过，零失败；APK构建和lint通过，保留{m['android_lint']['Warning']}项警告。
- 完整Gowin综合及布局布线通过：Logic {m['resources']['Logic']}，BSRAM {m['resources']['BSRAM']}，DSP {m['resources']['DSP']}。音频目标12.288MHz，报告Fmax {m['fmax_mhz']}MHz。未把工具结果当作实机结论。
- 完整FPGA源码包已经检查相对路径、全部资源和预处理；完整板级构建由Gowin验证。

## 去借设备前后

建议借四通道示波器、三根10X探头，支持单次触发、A-B运算和CSV导出；差分探头可简化功放输出测量。测量前确认设备共地和供电正常。

1. 测量传感片进入ADC的信号；以事先约定的阈值越过为输入起点，不用LED亮起代替手指输入。
2. MAX98357A喇叭输出是桥接开关波形，喇叭负端不能接台式示波器地夹。两个普通探头地夹都接电路GND、探针分别测OUT+和OUT-后做A-B，且须确认探头/仪器允许这样测量；或使用合适差分探头。
3. 区分空闲PWM和真正音频。按实验室方法低通/解调后测输出包络，注明所用滤波延迟、噪声底与输出阈值。不能把PWM跳变当成出声，也不能通过双向滤波的预振铃提前判起音。
4. 先关闭效果，使用固定音量，两种音色、七片、轻/中/重、每组多次测试，记录中位数、P95和最大值；再补音效开启及多声部条件。保留原始波形和测量判据。
5. 若验收定义是“声音达到稳态的一定比例”，必须额外按该比例测，不能拿首个非零样本或本文阈值64来替代。

功放输出测量背景参考：[Analog Devices MAX98357A数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf)、[Adafruit模块输出说明](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts)。

## 文件与复现

- `声芯乐动_低延迟_完整音响版_20261101.fs`：未下载的完整候选固件。
- `声芯乐动_0.17_低延迟_双识别离线版.apk`：本次构建的APK。
- `低延迟_完整FPGA工程.zip`：解压后用Gowin V1.9.11.03 Education打开工程；或在解压目录执行gw_sh build.tcl。
- `source`：本次改动、脚本、测试与实现计划；其余Android项目仍在工作区app/android。
- `evidence`：完整RTL结果、数字延迟CSV/日志、PCM对照、Android报告、PNR时序和资源报告。`release.json`记录文件哈希和未烧录状态。

工作区复现：`python scripts/check_low_latency_20261101.py`；`python scripts/check_low_latency_pcm.py`；`python scripts/preflight_latency_20261101.py --source-build build/low_latency_20261101 --out build/low_latency_20261101/latency --all-octaves`；带`--fallback`运行完整峰值窗口对照；`python scripts/prepare_low_latency_20261101.py --build`构建FPGA。APK使用现有JDK17/Android SDK运行Gradle testDebugUnitTest assembleDebug lintDebug。
'''
(O/'低延迟改动与测试说明.md').write_text(text,encoding='utf8')
print(json.dumps({'portable_sources':len(files),'relative_assets_checked':refs,'user_code':m['user_code'],'readme_written':True},ensure_ascii=False))
