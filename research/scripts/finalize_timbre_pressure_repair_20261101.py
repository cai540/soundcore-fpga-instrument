"""Package a timing-clean complete speaker candidate; never program hardware."""
from pathlib import Path
import hashlib,html,json,re,shutil
from check_organic_build import timing

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/timbre_pressure_repair_20261101'
OUT=ROOT/'output/timbre_pressure_repair_20261101';OUT.mkdir(parents=True,exist_ok=True)
NAME='soundcore_speaker_omr_60k';PNR=BUILD/'impl/pnr'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tests=json.loads((BUILD/'tests.json').read_text(encoding='utf-8'))
assert len(tests)==15 and all(t['passed'] for t in tests)
for n in ['audition_tests.json','spectral_tests.json']:
    assert all(t['passed'] for t in json.loads((BUILD/n).read_text(encoding='utf-8')))
audio=json.loads((BUILD/'audio_validation.json').read_text(encoding='utf-8'))
assert audio['real_verilog_capture'] and len(audio['previews'])==4
inputs=json.loads((BUILD/'frozen_inputs.json').read_text(encoding='utf-8'))
assert all(sha(BUILD/'src'/name)==digest for name,digest in inputs.items())
meta=json.loads((BUILD/'build_metadata.json').read_text(encoding='utf-8'))
assert not meta['sram_written'] and not meta['flash_written']
asset_map={k:v['path'] for k,v in meta['asset_records'].items()}
for record in meta['source_records']:
    if record['modified']:continue
    old=Path(record['origin']);new=BUILD/'src'/record['relative']
    if new.suffix in ('.v','.vh'):
        expected=old.read_text(encoding='utf-8')
        for a,b in asset_map.items():expected=expected.replace(a,b)
        assert new.read_text(encoding='utf-8')==expected,record['relative']
    else:assert sha(new)==sha(old),record['relative']

def ports(path):
    body=path.read_text();start=body.index('name="Pinout_by_Port_Name"');section=body[start:body.index('</table>',start)]
    result={}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>',section,re.S):
        cells=[html.unescape(re.sub('<[^>]+>','',cell)).strip() for cell in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
        if len(cells)>=5 and cells[0]!='Port Name':result[cells[0]]=cells[2].split('/')[0]
    return result
actual_ports=ports(PNR/(NAME+'.pin.html'))
old_ports=ports(ROOT/'build/k5_lamp_follow_20261101/impl/pnr'/(NAME+'.pin.html'))
assert actual_ports and actual_ports==old_ports,'Public pinout differs from EAE0'
data=timing((PNR/(NAME+'_tr_content.html')).read_text())
assert not any(data['violations'].values()) and min(data['setup_slack_ns'],data['hold_slack_ns'])>=0
resources={};text=(PNR/(NAME+'.rpt.txt')).read_text()
for key in ['Logic','Register','BSRAM','DSP']:
    match=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',text,re.M);assert match,key
    used,total=float(match[1]),int(match[2]);assert used<=total
    resources[key]={'used':used,'total':total}
assert 'Bitstream generation completed' in (BUILD/'build.log').read_text(encoding='utf-8-sig')
firmware=OUT/'声芯乐动_音色降噪与7号力度_20261101.fs';shutil.copy2(PNR/(NAME+'.fs'),firmware)
code=re.search(r'//UserCode:\s*(\S+)',firmware.read_text())[1]
for source,name in [('harmonica_before_then_after.mp3','口琴_前旧后新.mp3'),('erhu_before_then_after.mp3','二胡_前旧后新.mp3'),
                    ('harmonica_new.mp3','口琴_修订版.mp3'),('erhu_new.mp3','二胡_修订版.mp3')]:shutil.copy2(BUILD/source,OUT/name)
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for name in ['tests.json','spectral_tests.json','audition_tests.json','audio_validation.json','frozen_inputs.json','build_metadata.json']:
    shutil.copy2(BUILD/name,evidence/name)
for source,name in [(NAME+'_tr_content.html','timing_report.html'),(NAME+'.rpt.txt','resource_report.txt'),(NAME+'.pin.html','pin_report.html')]:shutil.copy2(PNR/source,evidence/name)
for config in ['expression_profile_v2.json','pressure_profile_ai6_20261101.json']:shutil.copy2(ROOT/'config'/config,OUT/config)
report={'status':'complete_candidate_ready_for_sram_listening','firmware':str(firmware),'sha256':sha(firmware),'user_code':code,
    'baseline_user_code':'0x0000EAE0','sram_written':False,'flash_written':False,'hardware_scan_performed':False,
    'physical_audio_verified':False,'real_ai6_maximum_verified':False,'ai6_calibration_is_estimated':True,
    'pressure_input_scale_q12':[4096]*6+[4544],'pressure_profile_id':'fbb94330','pins_unchanged':True,'pins':actual_ports,
    'tests':tests,'spectral_cases':630,'pressure_mapping_cases':28672,'audio_validation':audio,
    'resources':resources,**data,'frozen_source_files':len(inputs),'shared_pitch_preserved':True,
    'actual_expression_completion_clocks':225,'audio_frame_clocks':256}
(OUT/'release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(BUILD/'release.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'build/latest_timbre_pressure_candidate.json').write_text(json.dumps({k:report[k] for k in ['status','firmware','sha256','user_code','baseline_user_code','sram_written','flash_written']},ensure_ascii=False,indent=2),encoding='utf-8')
note=f'''声芯乐动：音色与7号压力片修订候选
2026-11-01 · UserCode {code} · 完整MAX98357A外放固件 · 尚未烧录

口琴在强力度下的二次/三次谐波此前最高约为基音的1.13/0.99倍，新参数约0.447/0.189倍，恢复以基音为主的声音。二胡保留较丰富的弦乐谐波，但削弱过度尖涩的高次成分。随机纹理增益再降低16倍；数字消融测得残余约占长音RMS的0.047%/0.052%。强按窗口的新旧整体响度差只有-0.014/+0.009dB，不以降低整体音量掩盖。是否更像真实乐器仍需实际试听。

试听：每份“前旧后新”音频前6秒为当前EAE0参数，静音0.5秒，后6秒为修订参数。两段使用相同旋律、力度、包络与试听增益。来自实际Verilog运行的单声部数字输出，不是喇叭录音；完整固件的32声部排程另有回归。单独“修订版”为后6秒。

7号片：旧4306/4096仅依据端子1.95V对2.05V初步估算，仍未达到现场满格。新候选根据“约2/3柱高”把该路归一化调为4544/4096；在当前曲线下，满力度所需的零点扣除ADC增量从1071降至1015。此值是估计，不是新测量，仍需按压实板确认。其他六路与基础曲线保持。发声起音、持续力度、OLED/App柱高都读取同一映射，不只把图形拉高。

参数已保存在两个JSON及候选固件中，不必每次手动重做；开机原有自动空载采样保留。实际测试应先松开七片开机，等约2秒，再正常按压7号；不需要异常用力。

检查：15项集成/定向回归、630个音色组合、28672条压力映射及真实RTL试听通过；共享音高16384种参数与旧实现1200帧PCM等价检查通过。完整布局布线Setup/Hold零违规，余量{data['setup_slack_ns']:+.3f}/{data['hold_slack_ns']:+.3f}ns。新表情路径仍225/256拍，32个独立声部。

本候选以EAE0完整版本为基线，保留七灯A8/B8/A9/B9/B11/A12/B12、K5灯环B10、五键、OLED、蓝牙、两首歌和识谱模块；实际引脚报告逐一相同。App无需为此重新安装。正常测试先关闭回声/合唱/混响，以较低音量分别听口琴和二胡，再看7号柱能否满格并随减压下降。

本轮没有硬件扫描、SRAM下载或Flash写入。建议下一次先下载SRAM试听，满意后再决定是否覆盖Flash。数字输出空载为0；若完全不弹时音响仍有同样沙声，还需单独定位模拟功放/供电噪声，不能用仿真宣称硬件已排除。
'''
(OUT/'试听与验收说明.txt').write_text(note,encoding='utf-8')
(OUT/'SHA256.json').write_text(json.dumps({p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256.json'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['firmware','user_code','sha256','setup_slack_ns','hold_slack_ns','resources']},ensure_ascii=False,indent=2))
