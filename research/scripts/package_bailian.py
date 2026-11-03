"""Package the verified backend change; keep the unchanged APK and secrets separate."""
from pathlib import Path
import hashlib,json,shutil,zipfile,xml.etree.ElementTree as ET


def main():
    root=Path(__file__).resolve().parents[1]
    build=root/'build/bailian_20261030';out=root/'output/bailian_20261030';out.mkdir(parents=True,exist_ok=True)
    probe=json.loads((build/'probe/result.json').read_text(encoding='utf8'))
    comparisons=json.loads((build/'ab_report.json').read_text(encoding='utf8'))
    assert probe['succeeded'] and all(v['same_pitch_sequence'] for v in comparisons)
    assert 'Ran 67 tests' in (build/'tests_verified.log').read_text(encoding='utf8')
    assert (build/'tests_verified.log').read_text(encoding='utf8').rstrip().endswith('OK')
    android=ET.parse(root/'app/android/app/build/test-results/testDebugUnitTest/TEST-cn.soundcore.instrument.ScoreApiTest.xml').getroot()
    assert android.attrib['failures']==android.attrib['errors']=='0'
    rtl=json.loads((build/'android_fixture/validation.json').read_text());assert rtl['passed']
    health=json.loads((build/'approved_health.json').read_text());assert health['ready'] and health['speech_provider']=='bailian'
    paths=[]
    for folder in ['score_api','soundcore_audio']:
        paths.extend(p for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts)
    paths.extend(root/p for p in ['config/score_api_bailian.json','config/score_api_models.json','scripts/start_score_api.ps1',
        'scripts/probe_bailian.py','scripts/check_score_api.py','scripts/check_score_api_endpoint.py','scripts/package_bailian.py',
        'tests/test_bailian.py','tests/test_score_api.py','docs/百炼云端识谱接入.md','docs/API识谱使用说明.md','docs/API识谱协议.md'])
    archive=out/'百炼识谱服务源码与配置.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(root).as_posix())
    secrets=[p.read_text(encoding='utf-8-sig').strip().encode('utf8') for p in (root/'.score-api').glob('*.key') if p.stat().st_size]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(not n.startswith('.score-api/') for n in z.namelist())
        assert all(secret not in z.read(n) for n in z.namelist() for secret in secrets)
    shutil.copy2(root/'docs/百炼云端识谱接入.md',out/'百炼云端识谱接入.md')
    calls=[probe['usage']]+[v['usage'] for v in comparisons]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report={'provider':'bailian','model':'qwen3-asr-flash','region':'cn-beijing',
        'real_cloud_requests':4,'requested_audio_seconds':128,'returned_total_tokens':sum(v['total_tokens'] for v in calls),
        'probe':probe,'comparisons':comparisons,'python_tests':67,
        'android_contract_tests':{k:int(android.attrib[k]) for k in ['tests','failures','errors','skipped']},
        'rtl':rtl,'health':health,'apk_runtime_changed':False,'fpga_flashed':False,
        'phone_wifi_ble_oled_tested':False,'pitch_accuracy_improvement_claimed':False,
        'source_sha256':digest(archive),'credentials_in_archive':False,
        'existing_apk_sha256':digest(root/'output/score_api_20261030/声芯_API识谱_v0.10.apk')}
    (out/'实测与验证记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'output':str(out),'real_requests':report['real_cloud_requests'],
        'returned_total_tokens':report['returned_total_tokens'],'same_pitch_sequences':len(comparisons)},ensure_ascii=False))


if __name__=='__main__':main()
