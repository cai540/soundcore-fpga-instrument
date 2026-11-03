"""Gate the speaker candidate on real PNR reports and the affected RTL checks."""
from pathlib import Path
from lxml import html
import argparse,hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--build-dir',default='build/speaker_omr_20261031')
parser.add_argument('--output-dir',default='output/speaker_omr_20261031')
parser.add_argument('--firmware-name',default='soundcore_外放完整识谱版_20261031.fs')
args=parser.parse_args()
BUILD=ROOT/args.build_dir;OUT=ROOT/args.output_dir
PNR=BUILD/'impl/pnr';NAME='soundcore_speaker_omr_60k'
tests=json.loads((BUILD/'tests.json').read_text(encoding='utf-8'))
meta=json.loads((BUILD/'build_metadata.json').read_text(encoding='utf-8'))
required={'tb_i2s_stereo_tx','tb_expression_speaker_core','tb_panel_audio_integration','tb_playable_synth32'}
if meta.get('uniform_pad_velocity'):
    required.update({'tb_seven_pad_full_scale','tb_pressure_expression32',
                     'tb_pressure_calibrated_profile' if meta.get('calibrated_input_scale_q12') else 'tb_pressure_saved_profile'})
assert len(tests)==len(required) and {t['test']for t in tests}==required and all(t['passed']for t in tests)
if meta.get('rtl_unchanged_verified'):
    proof=json.loads((BUILD/'verification_reuse.json').read_text(encoding='utf-8'))
    assert tests==json.loads(Path(meta['tests_reused_from']).read_text(encoding='utf-8'))
    for item in proof['files']:
        path=Path(item['external_input']) if 'external_input' in item else BUILD/'baseline'/item['file']
        digest=item['sha256'] if 'external_input' in item else item['snapshot_sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,str(path)
if meta.get('oled_recovery'):
    oled_tests=json.loads((BUILD/'oled_tests.json').read_text(encoding='utf-8'))
    assert len(oled_tests)==8 and all(t['passed']for t in oled_tests)
    proof=json.loads((BUILD/'verification_reuse.json').read_text(encoding='utf-8'))
    for item in proof['files']:
        path=Path(item['external_input']) if 'external_input'in item else BUILD/'baseline'/item['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item.get('sha256',item.get('snapshot_sha256'))
    assert tests==json.loads(Path(meta['tests_reused_from']).read_text(encoding='utf-8'))
    meta['oled_tests']=oled_tests
if meta.get('panel_menu_fix'):
    menu_tests=json.loads((BUILD/'panel_menu_tests.json').read_text(encoding='utf-8'))
    assert len(menu_tests)==(11 if meta.get('panel_native_transport') else 9) and all(t['passed']for t in menu_tests)
    assert 'tb_panel_oled_menu_flow' in {t['test']for t in menu_tests}
    if meta.get('panel_native_transport'):
        assert {'tb_native_panel_transport','tb_native_panel_oled_flow','tb_native_demo_audio'} <= {t['test']for t in menu_tests}
    proof=json.loads((BUILD/'verification_reuse.json').read_text(encoding='utf-8'))
    for item in proof['files']:
        path=Path(item['external_input']) if 'external_input'in item else BUILD/'baseline'/item['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item.get('sha256',item.get('snapshot_sha256'))
    assert tests==json.loads(Path(meta['tests_reused_from']).read_text(encoding='utf-8'))
    meta['panel_menu_tests']=menu_tests
if meta.get('k5_lamp_follow'):
    lamp_tests=json.loads((BUILD/'lamp_tests.json').read_text(encoding='utf-8'))
    assert lamp_tests and all(t['passed']for t in lamp_tests)
    assert menu_tests==json.loads(Path(meta['panel_tests_reused_from']).read_text(encoding='utf-8'))
    meta['lamp_tests']=lamp_tests
report=(PNR/(NAME+'.rpt.txt')).read_text(encoding='utf-8')
resources={}
for key in ['Logic','Register','BSRAM','DSP']:
    match=re.search(r'^\s*'+key+r'\s+\|\s+([\d.]+)/([\d.]+)',report,re.M);assert match,key
    used,total=map(float,match.groups());assert used<=total;resources[key]={'used':used,'total':total}
tree=html.fromstring((PNR/(NAME+'_tr_content.html')).read_bytes());violations={};slacks={}
for row in tree.xpath('//tr'):
    cells=[' '.join(c.text_content().split())for c in row.xpath('./td')]
    if len(cells)==2 and 'Violated'in cells[0]:violations[cells[0]]=int(cells[1])
assert violations and not any(violations.values()),violations
for kind in ['Setup','Hold']:
    tables=tree.xpath(f'//a[@name="{kind}_Slack_Table"]/../following-sibling::table[1]');assert tables
    values=[float(row.xpath('./td')[1].text_content())for row in tables[0].xpath('.//tr')if len(row.xpath('./td'))>1]
    slacks[kind]=min(values);assert slacks[kind]>=0
cst=BUILD/'baseline/board/soundcore_speaker_omr_60k.cst'
expected=dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);',cst.read_text(encoding='utf-8')))
actual={}
for row in html.fromstring((PNR/(NAME+'.pin.html')).read_bytes()).xpath('//tr'):
    cells=[c.text_content().strip()for c in row.xpath('./td')]
    if len(cells)>=8 and cells[0]in expected and '/'in cells[2]:actual[cells[0]]=cells[2].split('/')[0]
assert actual==expected,(actual,expected)
if meta.get('lamp_drive_ma'):
    drive_check=json.loads((BUILD/'lamp_drive_report_check.json').read_text(encoding='utf-8'))
    assert drive_check['passed'] and drive_check['all_other_port_properties_unchanged']
    pin_rows=html.fromstring((PNR/(NAME+'.pin.html')).read_bytes()).xpath('//tr')
    lamp_rows=[[c.text_content().strip()for c in row.xpath('./td')]for row in pin_rows]
    lamp=[c for c in lamp_rows if len(c)==20 and c[0]=='guide_button_led_o']
    assert len(lamp)==1 and lamp[0][2]=='B17/1' and lamp[0][7]=='LVCMOS33'
    assert lamp[0][8]==str(meta['lamp_drive_ma']) and lamp[0][17]=='3.3'
    meta['lamp_drive_report_verified']=True
syn=(BUILD/'impl/gwsynthesis'/(NAME+'.log')).read_text(encoding='utf-8')
assert "Compiling module 'i2s_stereo_tx'"in syn
assert "Compiling module 'pt8211_tx_12m288"not in syn
wrapper=(BUILD/'baseline/board/soundcore_melody_top.v').read_text(encoding='utf-8')
assert '.HEADPHONE_OUTPUT(0)'in wrapper and 'CONTINUOUS_EXPRESSION=1'in syn
if meta.get('oled_recovery') or meta.get('panel_menu_fix'):
    product=(BUILD/'baseline/board/pressure_i2s_panel_oled_ble_experiment_top.v').read_text(encoding='utf-8')
    assert '.OMR_ENABLE(1)'in product, 'Complete product must keep OMR endpoint enabled'
    assert 'omr_symbol_mlp'in syn, 'OMR module must survive elaboration'
if meta.get('panel_native_transport'):
    assert "Compiling module 'front_panel_product'" in syn
    assert '.player_command_valid(local_player_valid)' in product
    assert '.command_valid(player_command_valid)' in product
    assert '.menu_song(menu_song_index)' in product
OUT.mkdir(parents=True,exist_ok=True)
firmware=PNR/(NAME+'.fs');header=firmware.read_bytes()[:1600].decode('ascii',errors='replace')
code=re.search(r'UserCode:\s*(0x[0-9a-fA-F]+)',header).group(1)
target=OUT/args.firmware_name;shutil.copyfile(firmware,target)
meta.update(status='built_and_routed_speaker_candidate',firmware=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            user_code=code,resources=resources,violations=violations,slack_ns=slacks,tests=tests,
            routed_pins_verified=True,standard_i2s_selected=True,physical_audio_verified=False,
            apk_unchanged=True,programming_allowed=True)
(OUT/'release.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
sources=[cst,BUILD/'baseline/board/soundcore_melody_top.v',BUILD/'baseline/rtl/front_panel_five_keys.v']
if meta.get('uniform_pad_velocity'):
    sources.extend([BUILD/'baseline/board/pressure_i2s_additive32_core.v',BUILD/'baseline/rtl/pressure_expression32.v'])
if meta.get('calibrated_input_scale_q12'):
    sources.extend([BUILD/'baseline/rtl/fsr_strike_detector.v',BUILD/'baseline/rtl/pressure_profile_curve.vh',
                    BUILD/'baseline/rtl/pressure_profile_config.vh',BUILD/'baseline/config/pressure_profile_ai6_20261031.json'])
for p in sources:
    dst=OUT/'modified_source'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(p,dst)
for p in [PNR/(NAME+'.rpt.txt'),PNR/(NAME+'_tr_content.html'),PNR/(NAME+'.pin.html'),BUILD/'tests.json']:
    dst=OUT/'evidence'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(p,dst)
for name in ['verification_reuse.json','led_layout.json','oled_tests.json','panel_menu_tests.json','lamp_tests.json','lamp_drive_report_check.json','lamp_electrical_check.json']:
    if (BUILD/name).exists():shutil.copyfile(BUILD/name,OUT/'evidence'/name)
if meta.get('oled_recovery') or meta.get('panel_menu_fix'):
    for name in meta['modified_copied_files']:
        shutil.copyfile(BUILD/'baseline'/name,OUT/'modified_source'/Path(name).name)
readme='''外放完整识谱版（2026-10-31）

恢复原来的MAX98357A标准I2S外放。BCLK/LRC/DIN沿用原接线，其余26个共用接口位置不变；不需要为了改外放而移动ADC、OLED、蓝牙、LED或面板按钮。
保留早期力度、持续表情、曲谱上传、OLED流程与FPGA识谱核；APK仍使用0.12，不需要换包。
启动音量6/31。外放与先前耳机额外1/4衰减不是相同增益路径，先低音量试敲。
本候选仅下载SRAM，不写Flash；下载结果以programming_sram.json记录为准。编译、仿真与下载成功均不代表实际音箱已经有声，仍需听音验收。
共享音高、曲库、模型与算法逻辑保留。耳机旧候选单独保存，没有覆盖原二进制。
'''
(OUT/'使用说明.txt').write_text(readme,encoding='utf-8-sig')
if meta.get('uniform_pad_velocity'):
    readme=readme.replace('其余26个共用接口位置不变','其余22个非LED接口位置不变').replace('不需要为了改外放而移动ADC、OLED、蓝牙、LED或面板按钮。','七灯需按'+ '/'.join(meta['led_positions'])+'换线；ADC、音响、OLED、蓝牙及面板按钮不动。')
    readme+='\n删除1号片的旧力度减半，并让持续表情到达0/255端点；七路满力度回归通过。不凭仿真声称7号实体片已修复。尚未下载，必须在换线与版本对应后测试。\n'
    if meta.get('calibrated_input_scale_q12'):
        readme+='7号AI6按实测1.95V与参考2.05V做曲线前初步量程归一化，Q12系数4306/4096；其他六路4096/4096。使用原自动空载零点；假设模拟前端近似线性、端子空载近0，未把电压当ADC绝对码。参数已存固件，真实最大力度和听感仍需验收。\n'
    (OUT/'使用说明.txt').write_text(readme,encoding='utf-8-sig')
(OUT/'SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file()and p.name!='SHA256.json'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'firmware':str(target),'user_code':code,'resources':resources,'slack_ns':slacks,'affected_tests':len(tests),'pins_verified':len(actual)},ensure_ascii=False))
