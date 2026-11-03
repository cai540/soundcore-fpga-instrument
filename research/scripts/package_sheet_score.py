"""Deliver the checked image/audio App without keys, recordings or model weights."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,zipfile,xml.etree.ElementTree as ET


def main():
    root=Path(__file__).resolve().parents[1]
    build=root/'build/sheet_score_20261030';out=root/'output/sheet_score_20261030';out.mkdir(parents=True,exist_ok=True)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert 'BUILD SUCCESSFUL' in (build/'android_delivery.log').read_text(encoding='utf8')
    py=(build/'python_release_check.log').read_text(encoding='utf8')
    assert py.rstrip().endswith('OK') and 'Ran 80 tests' in py
    totals={k:0 for k in ('tests','failures','errors','skipped')}
    for p in (root/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
        suite=ET.parse(p).getroot()
        for k in totals:totals[k]+=int(suite.attrib.get(k,0))
    assert totals['tests']>=219 and totals['failures']==totals['errors']==0
    lint=(root/'app/android/app/build/reports/lint-results-debug.txt').read_text(encoding='utf8')
    lint_count=re.search(r'(\d+) errors, (\d+) warnings',lint);assert lint_count and lint_count[1]=='0'
    vision=json.loads((build/'vision_validation.json').read_text());assert vision['passed']
    rtl={}
    for folder in ('android_fixture','real_android_fixture'):
        rtl[folder]=json.loads((build/folder/'validation.json').read_text())
        assert rtl[folder]['passed'] and not rtl[folder]['physical_hardware_test']
    apk=out/'声芯_录音与图片识谱_v0.11.apk'
    shutil.copy2(root/'app/android/app/build/outputs/apk/debug/app-debug.apk',apk)
    tool=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0')
    verified=subprocess.run([str(tool/'apksigner.bat'),'verify','--verbose','--print-certs',str(apk)],capture_output=True,text=True)
    assert verified.returncode==0,verified.stderr
    (build/'apk_signature.txt').write_text(verified.stdout,encoding='utf8')
    cert=lambda s:next(v for v in s.splitlines() if 'certificate SHA-256 digest:' in v).split(':',1)[1].strip()
    assert cert(verified.stdout)==cert((build/'prior_apk_signature.txt').read_text(encoding='utf8'))
    manifest=subprocess.run([str(tool/'aapt2.exe'),'dump','badging',str(apk)],capture_output=True,text=True,encoding='utf8')
    assert manifest.returncode==0 and "versionCode='11'" in manifest.stdout and "versionName='0.11-sheet-score'" in manifest.stdout
    (build/'apk_badging.txt').write_text(manifest.stdout,encoding='utf8')
    firmware=root/'build/soundcore_headphone_melody_20261028.fs'
    assert sha(firmware)=='ff9d5fe5ed3f8bb2944e9b268c46efba484c9d1d72e0af4f72afec62023aacb3'
    shutil.copy2(root/'docs/录音演奏与AI图片识谱.md',out/'使用说明.md')
    paths=[]
    for name in ('score_api','soundcore_audio','app/android/app/src','tests'):
        paths.extend(p for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths.extend(root/p for p in ['.gitignore','config/score_api_bailian.json','config/score_api_models.json',
        'scripts/start_score_api.ps1','scripts/check_sheet_api.py','scripts/check_score_api.py','scripts/check_score_api_endpoint.py',
        'scripts/package_sheet_score.py','docs/录音演奏与AI图片识谱.md','docs/API识谱协议.md',
        'app/android/build.gradle.kts','app/android/settings.gradle.kts','app/android/gradle.properties','app/android/app/build.gradle.kts',
        'rtl/uploaded_song_engine.v','rtl/ble_control_endpoint.v','rtl/ble_frame_parser.v','tb/tb_melody_upload_endpoint.v'])
    archive=out/'录音与图片识谱源码_v0.11.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(set(paths)):z.write(p,p.relative_to(root).as_posix())
    keys=[p.read_text(encoding='utf-8-sig').strip().encode() for p in (root/'.score-api').glob('*.key') if p.stat().st_size]
    for artifact in (apk,archive):
        with zipfile.ZipFile(artifact) as z:
            assert z.testzip() is None
            assert all(not n.startswith('.score-api/') and not n.endswith(('.f32','.mp3','.wav','.onnx','.pt')) for n in z.namelist())
            assert all(secret not in z.read(n) for n in z.namelist() for secret in keys)
    calls=[json.loads((build/f/'http_result.json').read_text(encoding='utf8'))['result']
        for f in ('simple_retry_after_sync_http','duration_checked_http')]
    report={'version':'0.11-sheet-score','apk_sha256':sha(apk),'source_zip_sha256':sha(archive),
        'same_signer_as_v010':True,'signing_certificate_sha256':cert(verified.stdout),'android_unit_tests':totals,
        'python_tests':80,'lint_errors':0,'lint_warnings':int(lint_count[2]),'vision':vision,
        'real_successful_vision_requests_this_retry':2,'returned_tokens_this_retry':sum(c['cloud_usage']['total_tokens'] for c in calls),
        'first_success_had_duration_errors':True,'corrected_prompt_second_success_matches_test_sheet':True,
        'android_http_test_uses_stub':True,'rtl_simulation':rtl,'credentials_in_artifacts':False,
        'flashed':False,'firmware_unchanged_sha256':sha(firmware),'phone_native_ui_verified':False,
        'physical_wifi_ble_oled_audio_test':False,'complex_or_unseen_score_accuracy_measured':False,
        'sheet_api_requires_running_proxy':True,'audio_pitch_models_moved_to_phone':False}
    (out/'验证记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'开始使用.txt').write_text('声芯乐动 v0.11\n\n安装APK → 曲目 → AI曲谱识别 → 选择图片 → AI识别 → 选择片段 → 载入 → 试听/传入设备。\n'
        '录音演奏入口单独保留。手机与电脑同Wi-Fi，继续使用已有识谱服务地址和连接码。\n'
        '电脑启动：\npowershell -ExecutionPolicy Bypass -File D:\\FPGA\\Projects\\soundcore_2026\\scripts\\start_score_api.ps1 -Lan -CopyConnectionCode\n\n'
        '真实百炼图片调用已成功；简单测试谱的音高与时值已核对。复杂长谱、手机界面和蓝牙/OLED实物仍待验收。没有烧录。\n'
        '详细步骤和限制见使用说明.md；密钥未放入APK或源码包。\n',encoding='utf8')
    print(json.dumps({'output':str(out),'apk_bytes':apk.stat().st_size,'sources':len(set(paths)),'android':totals,
        'python_tests':80,'real_cloud_tokens':report['returned_tokens_this_retry']},ensure_ascii=False))


if __name__=='__main__':main()
