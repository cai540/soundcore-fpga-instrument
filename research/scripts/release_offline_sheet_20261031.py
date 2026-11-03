"""Package the API-free image path and explicit, non-hardware verification evidence."""
from pathlib import Path
import hashlib,json,shutil,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/offline_sheet_full_20261031'
SITE=ROOT/'web/phone-lab-20261030'
EVIDENCE=ROOT/'build/offline_ocr_20261031'
OUT.mkdir(parents=True,exist_ok=True)
def copy(source,target):
    target=OUT/target;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)

apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
copy(apk,Path('声芯乐动_0.12_离线识谱.apk'))
copy(ROOT/'output/fpga_omr_20261031/soundcore_含FPGA识谱核_待上板.fs',Path('soundcore_含FPGA识谱核_待上板.fs'))
copy(ROOT/'docs/offline_sheet_full_20261031.md',Path('使用说明与验收边界.md'))
for folder in ['lib','tests','app','scripts']:
    for p in (SITE/folder).rglob('*'):
        if p.is_file():copy(p,Path('source/web/phone-lab-20261030')/p.relative_to(SITE))
for name in ['package.json','package-lock.json','tsconfig.json','vite.config.ts','next.config.ts','postcss.config.mjs','cloudflare-env.d.ts']:
    copy(SITE/name,Path('source/web/phone-lab-20261030')/name)
for p in (SITE/'public/offline').rglob('*'):
    if p.is_file():copy(p,Path('source/web/phone-lab-20261030')/p.relative_to(SITE))
android=ROOT/'app/android'
for folder in ['app/src']:
    for p in (android/folder).rglob('*'):
        if p.is_file():copy(p,Path('source/app/android')/p.relative_to(android))
for name in ['app/build.gradle.kts','settings.gradle.kts','build.gradle.kts','gradle.properties']:
    copy(android/name,Path('source/app/android')/name)
for name in ['build_offline_sheet_assets.mjs','release_offline_sheet_20261031.py','check_offline_sheet_production_20261031.py']:
    copy(ROOT/'scripts'/name,Path('source/scripts')/name)
for folder in ['src','baseline']:
    for p in (ROOT/'build/fpga_omr_20261031'/folder).rglob('*'):
        if p.is_file():copy(p,Path('fpga_evidence/build_inputs')/folder/p.relative_to(ROOT/'build/fpga_omr_20261031'/folder))
for name in ['full_pipeline_evidence.json','native_bridge_browser_evidence.json','android_validation.json',
             'production_validation.json','site_deployment.json','native_contract_cases.json',
             'benchmark_compact.json','asset-manifest.json','README.md','phone_offline_ui.png']:
    copy(EVIDENCE/name,Path('evidence')/name)
for p in (ROOT/'output/fpga_omr_20261031').rglob('*'):
    if p.is_file() and p.suffix!='.zip':copy(p,Path('fpga_evidence')/p.relative_to(ROOT/'output/fpga_omr_20261031'))
results=[ET.parse(p).getroot().attrib for p in (android/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
tests={k:sum(int(r.get(k,0))for r in results)for k in ['tests','failures','errors','skipped']}
assert tests['tests']>=225 and tests['failures']==0 and tests['errors']==0
manifest={'status':'image_api_runtime_removed_phone_fpga_pipeline_integrated_acceptance_pending',
 'apk_version':'0.12-fpga-offline-sheet','apk_version_code':12,'android_tests':tests,
 'image_inference':{'symbol':'fpga_binary_mlp_256_64_11','text':'phone_local_tesseract_wasm','external_api_required':False},
 'recording_asr_api_replaced':False,'trained_model_crc32':3866258960,
 'physical_board_verified':False,'android_webview_device_verified':False,'sram_written':False,'flash_written':False,
 'full_page_accuracy_verified':False,'fully_accepted_replacement':False,
 'website_url':'https://soundcore-phone-lab-1030.liuwencai05.chatgpt.site/'}
manifest['website_source_commit']=json.loads((EVIDENCE/'site_deployment.json').read_text(encoding='utf-8'))['commit_sha']
(OUT/'release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
digests={str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
         for p in OUT.rglob('*')if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json'}
(OUT/'SHA256.json').write_text(json.dumps(digests,ensure_ascii=False,indent=2),encoding='utf-8')
# Compare actual local secrets without logging them or copying their source files.
secrets=[]
for p in (ROOT/'.score-api').glob('*'):
    if p.is_file() and p.suffix in ['.key','.json']:
        if p.suffix=='.key':secrets.append(p.read_bytes().strip())
        else:
            try:
                value=json.loads(p.read_text(encoding='utf-8'))
                if isinstance(value,dict):secrets += [v.encode()for k,v in value.items()if isinstance(v,str) and any(s in k.lower()for s in ['token','key','secret'])]
            except (ValueError,UnicodeError):pass
secrets=[s for s in secrets if len(s)>=16]
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix!='.zip':
        data=p.read_bytes();assert not any(secret in data for secret in secrets),'Secret found in release'
archive=OUT/'声芯乐动_离线识谱_软件与固件候选包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
    for p in OUT.rglob('*'):
        if p.is_file() and p.suffix!='.zip':z.write(p,p.relative_to(OUT))
with zipfile.ZipFile(archive)as z:
    assert z.testzip()is None
    for name,digest in digests.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
print(json.dumps({'android_tests':tests,'files':len(digests),'archive_bytes':archive.stat().st_size,'secrets_scan_passed':True},ensure_ascii=False))
