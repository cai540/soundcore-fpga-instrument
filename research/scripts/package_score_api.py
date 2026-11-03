"""Package verified App/API sources without connection codes, recordings or weights."""
from pathlib import Path
import hashlib, json, re, shutil, zipfile, xml.etree.ElementTree as ET

def main():
    ROOT=Path(__file__).resolve().parents[1]
    BUILD=ROOT/'build/score_api_20261030'
    OUT=ROOT/'output/score_api_20261030'
    OUT.mkdir(parents=True,exist_ok=True)
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    log=(BUILD/'android_verified_build.log').read_text(encoding='utf8')
    assert 'BUILD SUCCESSFUL' in log
    totals={'tests':0,'failures':0,'errors':0,'skipped':0}
    for path in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
        suite=ET.parse(path).getroot()
        for k in totals:totals[k]+=int(suite.attrib.get(k,0))
    assert totals['tests']>=212 and totals['failures']==totals['errors']==0
    assert 'Ran 60 tests' in (BUILD/'python_tests.log').read_text(encoding='utf8')
    assert (BUILD/'python_tests.log').read_text(encoding='utf8').rstrip().endswith('OK')
    lint=(ROOT/'app/android/app/build/reports/lint-results-debug.txt').read_text(encoding='utf8')
    assert '0 errors' in lint
    live=json.loads((BUILD/'android_live_http.json').read_text())
    assert live['actual_android_http_client'] and live['pitch_sequence_identical']
    parity=json.loads((BUILD/'native_parity.json').read_text())
    assert all(item['exact_notes_identical'] for item in parity.values())
    rtl=json.loads((BUILD/'android_fixture/validation.json').read_text())
    assert rtl['passed'] and not rtl['physical_hardware_test']
    new_sig=(BUILD/'apk_signature.txt').read_text(encoding='utf8')
    old_sig=(BUILD/'prior_apk_signature.txt').read_text(encoding='utf8')
    cert=lambda s:next(x for x in s.splitlines() if 'certificate SHA-256 digest:' in x).split(':',1)[1].strip()
    assert cert(new_sig)==cert(old_sig)
    firmware=ROOT/'build/soundcore_headphone_melody_20261028.fs'
    assert digest(firmware)=='ff9d5fe5ed3f8bb2944e9b268c46efba484c9d1d72e0af4f72afec62023aacb3'
    apk=OUT/'声芯_API识谱_v0.10.apk'
    shutil.copy2(ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk',apk)
    for name in ['API识谱使用说明.md','API识谱协议.md']:
        shutil.copy2(ROOT/'docs'/name,OUT/name)

    roots=['score_api','soundcore_audio','app/android/app/src']
    files=[]
    for root in roots:
        files.extend(p for p in (ROOT/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    files.extend(ROOT/p for p in ['.gitignore','config/score_api_models.json','scripts/start_score_api.ps1',
        'scripts/check_score_api.py','scripts/check_score_api_endpoint.py','scripts/package_score_api.py',
        'tests/test_score_api.py','docs/API识谱使用说明.md','docs/API识谱协议.md',
        'app/android/build.gradle.kts','app/android/settings.gradle.kts','app/android/gradle.properties','app/android/app/build.gradle.kts'])
    archive=OUT/'API与App源码_v0.10.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(files)):z.write(p,p.relative_to(ROOT).as_posix())
    secret=(ROOT/'.score-api/service.key').read_bytes().strip()
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any('.score-api/' in n or n.endswith(('.onnx','.pt','.f32')) for n in z.namelist())
        assert all(secret not in z.read(n) for n in z.namelist())
    baseline=json.loads((BUILD/'baseline.json').read_text(encoding='utf8'))
    changed=[p for p,sha in baseline.items() if digest(ROOT/p)!=sha]
    report={'version':'0.10-score-api','apk_sha256':digest(apk),'source_zip_sha256':digest(archive),
        'apk_certificate_sha256':cert(new_sig),'same_signer_as_v09':True,'android':totals,
        'python_tests':60,'lint_errors':0,'lint_warnings':int(re.search(r'0 errors, (\d+) warnings',lint).group(1)),'live_android_client':live,
        'source_rate_http_regression':parity,'rtl':rtl,'firmware_unchanged_sha256':digest(firmware),
        'changed_baseline_files':changed,'flashed':False,'physical_wifi_ble_oled_test':False,
        'android_visual_render_verified':False,'held_out_accuracy_measured':False,
        'credentials_recordings_model_weights_in_source_zip':False}
    (OUT/'验证记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'开始使用.txt').write_text('声芯 API识谱 v0.10\n\n安装APK → 曲目 → 录一段，接着奏 → API识谱 → 设置识谱服务。\n'
        '电脑端启动：\n'
        'powershell -ExecutionPolicy Bypass -File D:\\FPGA\\Projects\\soundcore_2026\\scripts\\start_score_api.ps1 -Lan -CopyConnectionCode\n\n'
        '服务使用当前开发电脑上的模型，不含公共云端网址；手机与电脑需同Wi-Fi。详细步骤见API识谱使用说明.md。\n'
        '源码包不包含权重、音频或连接码；换电脑需准备模型与依赖。\n'
        '真实HTTP、Android客户端、协议测试及RTL仿真已通过。未烧录；手机收音、界面与蓝牙/OLED实机仍待验收。\n',encoding='utf8')
    print(json.dumps({'output':str(OUT),'android':totals,'apk_bytes':apk.stat().st_size,'sources':len(files)},ensure_ascii=False))



if __name__=='__main__':main()
