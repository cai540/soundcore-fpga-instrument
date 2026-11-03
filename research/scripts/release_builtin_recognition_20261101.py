"""Fail-closed offline APK/evidence packaging. Never programs the FPGA."""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
import hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/builtin_recognition_20261101'
OUT=ROOT/'output/builtin_recognition_20261101'
ANDROID=ROOT/'app/android'
SDK=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0')
JAVA=Path('D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1/bin/java.exe')
FFMPEG=Path('C:/Users/YOUR_USER/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe')
TITLES={'zuguo':'我和我的祖国','qiansixi':'牵丝戏','chilege':'敕勒歌'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(source,target):
    target=OUT/target;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
def command(args):return subprocess.check_output([str(a)for a in args],stderr=subprocess.STDOUT).decode('utf8',errors='replace')
def audition(ident):
    row=json.loads((BUILD/'audio'/f'{ident}_notes.json').read_text(encoding='utf8'))
    pcm=np.fromfile(BUILD/f'{ident}.f32',dtype='<f4');wave=np.zeros_like(pcm);phase=0.
    for n in row['notes']:
        a=n['start_ms']*16;z=min(len(pcm),(n['start_ms']+n['duration_ms'])*16);count=z-a
        assert count>0
        omega=2*np.pi*440*2**((n['midi']-69)/12)
        t=np.arange(count)/16000
        envelope=np.minimum(1,t/.012)*np.minimum(1,(count-1-np.arange(count))/16000/.018)
        wave[a:z]=.22*np.sin(phase+omega*t)*envelope
        phase=(phase+omega*count/16000)%(2*np.pi)
    audio=OUT/'试听';audio.mkdir(exist_ok=True)
    paths=[]
    for suffix,data in [('离线算法40秒',wave),('原声左_旋律右',np.column_stack([pcm*.8/max(.8,float(abs(pcm).max())),wave]))]:
        target=audio/f'{TITLES[ident]}_{suffix}.mp3';channels=1 if data.ndim==1 else 2
        subprocess.run([str(FFMPEG),'-v','error','-y','-f','f32le','-ar','16000','-ac',str(channels),'-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(target)],input=data.astype('<f4').tobytes(),check=True)
        decoded=np.frombuffer(subprocess.check_output([str(FFMPEG),'-v','error','-i',str(target),'-ar','16000','-ac',str(channels),'-f','f32le','-']),dtype='<f4')
        assert len(decoded)==data.size and np.isfinite(decoded).all() and abs(decoded).max()<.999
        paths.append({'file':str(target.relative_to(OUT)),'seconds':40,'sha256':sha(target)})
    return paths
def diagnostic():
    # Evaluation only. These old automatic unit times are NOT independent gold timing.
    reference=json.loads((ROOT/'evaluation/transcription/character_reference40_audited.json').read_text(encoding='utf8'))
    rows=[]
    for case in reference['cases']:
        ident=case['id'];units=json.loads((ROOT/'output/vocal_units40_20261030'/ident/'characters.json').read_text(encoding='utf8'))['units']
        gold=[u for phrase in case['phrases']for u in phrase['units']];metrics={}
        for label,suffix in [('legacy_v7','_legacy_notes.json'),('builtin_v8','_notes.json')]:
            notes=json.loads((BUILD/'audio'/(ident+suffix)).read_text(encoding='utf8'))['notes'];passed=0;errors=[]
            for i,(g,u)in enumerate(zip(gold,units)):
                a=u['notes'][0]['start_ms'];z=u['notes'][-1]['end_ms'];weights=Counter()
                for n in notes:
                    overlap=max(0,min(z,n['start_ms']+n['duration_ms'])-max(a,n['start_ms']))
                    if overlap:weights[n['midi']]+=overlap
                pitch=weights.most_common(1)[0][0]if weights else None
                ok=any(pitch in allowed for allowed in g['allowed_sequences']);passed+=ok
                if not ok:errors.append({'index':i,'character':g['character'],'allowed':g['allowed_sequences'],'dominant_overlap_pitch':pitch})
            metrics[label]={'covered_units':passed,'units':len(gold),'notes':len(notes),'issues':errors}
        assert metrics['builtin_v8']['covered_units']>=metrics['legacy_v7']['covered_units']
        rows.append({'case':ident,**metrics})
    return {'kind':'development_dominant_pitch_overlap_on_OLD_AUTOMATIC_unit_spans_NOT_word_accuracy',
        'independent_timing_gold':False,'syllable_count_accuracy_claimed':False,'musical_acceptance_passed':False,'cases':rows}
def main():
    OUT.mkdir(exist_ok=True)
    apk=ANDROID/'app/build/outputs/apk/debug/app-debug.apk'
    permissions=command([SDK/'aapt.exe','dump','permissions',apk])
    assert 'android.permission.INTERNET'not in permissions
    badging=command([SDK/'aapt.exe','dump','badging',apk]);assert "versionCode='15'"in badging and "versionName='0.15-offline'"in badging
    signer=command([JAVA,'-jar',SDK/'lib/apksigner.jar','verify','--print-certs',apk])
    previous=ROOT/'output/app_product_20261101/声芯乐动_0.14_全页面重设计.apk'
    old=command([JAVA,'-jar',SDK/'lib/apksigner.jar','verify','--print-certs',previous])
    digest=lambda text:next(line for line in text.splitlines()if 'certificate SHA-256 digest:'in line)
    assert digest(signer)==digest(old)
    assets=ANDROID/'app/src/main/assets';asset_hashes={}
    with ZipFile(apk)as z:
        for folder in ['offline','models','open_source_licenses']:
            for p in (assets/folder).rglob('*'):
                if p.is_file():
                    name='assets/'+str(p.relative_to(assets)).replace('\\','/')
                    assert z.read(name)==p.read_bytes(),name
                    asset_hashes[name]=sha(p)
        dex=b''.join(z.read(name)for name in z.namelist()if name.endswith('.dex'))
        for forbidden in ['dashscope.aliyuncs.com','trycloudflare.com','ScoreApiClient','ManagedRecognition','ScoreApiSettings']:
            assert forbidden.encode()not in dex and forbidden.encode('utf-16le')not in dex,forbidden
        abis=sorted({p.split('/')[1]for p in z.namelist()if p.startswith('lib/')})
        assert abis==['arm64-v8a','armeabi-v7a'],abis
    tests=[ET.parse(p).getroot().attrib for p in (ANDROID/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
    test_counts={k:sum(int(row.get(k,0))for row in tests)for k in ['tests','failures','errors','skipped']}
    assert test_counts['tests']>=248 and test_counts['failures']==test_counts['errors']==0
    lint=ET.parse(ANDROID/'app/build/reports/lint-results-debug.xml').getroot()
    assert not any(i.get('severity')=='Error'for i in lint.findall('issue'))
    sheet=json.loads((BUILD/'sheet_validation.json').read_text(encoding='utf8'))
    assert not sheet['non_local_requests'] and len(sheet['results'])==3
    report=diagnostic();(BUILD/'pitch_diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    dest=Path('声芯乐动_0.15_双识别内置离线版.apk');copy(apk,dest)
    for name in ['android_validation.log','android_final_build.log','android_delivery_build.log','asset_export.json','sheet_validation.json','pitch_diagnostic.json','js_tests.log','types.log']:
        copy(BUILD/name,Path('evidence')/name)
    copy(BUILD/'audio/report.json',Path('evidence/audio_runtime.json'))
    for ident in TITLES:
        copy(BUILD/'audio'/f'{ident}_notes.json',Path('evidence')/f'{ident}_notes.json')
        audition(ident)
    (OUT/'evidence/apk_permissions.txt').write_text(permissions,encoding='utf8')
    (OUT/'evidence/apk_signer.txt').write_text(signer,encoding='utf8')
    (OUT/'evidence/asset_hashes.json').write_text(json.dumps(asset_hashes,indent=2),encoding='utf8')
    for name in ['phoneRecordingWithoutConnection','phoneSheetWithoutConnection']:
        p=ANDROID/f'app/src/test/snapshots/images/cn.soundcore.instrument_OfflineRecognitionSnapshotsTest_{name}.png'
        copy(p,Path('screens')/(name+'.png'))
    source_files=['BuiltinMelodyRecognition.kt','CrepePitchObserver.kt','MelodyAudio.kt','MelodyRecognition.kt','VocalNoteSegmentation.kt','VocalMainNoteSegmentation.kt','OfflineSheetEngine.kt','SheetCapture.kt','SheetPanel.kt','MelodyPanel.kt','ScoreFields.kt','SheetMusic.kt']
    for name in source_files:copy(ANDROID/'app/src/main/java/cn/soundcore/instrument'/name,Path('source/android')/name)
    for name in ['phone-symbol-model.mjs','native-offline-entry.mjs','offline-sheet.mjs','header-accidental.mjs','header-ocr.mjs']:
        copy(ROOT/'web/phone-lab-20261030/lib'/name,Path('source/shared')/name)
    for name in ['prepare_builtin_recognition_20261101.py','check_builtin_sheet_20261101.cjs','release_builtin_recognition_20261101.py']:
        copy(ROOT/'scripts'/name,Path('source/scripts')/name)
    copy(assets/'models/crepe_tiny.json','source/models/crepe_tiny.json')
    copy(assets/'offline/symbol_model.json','source/models/symbol_model.json')
    release={'version':'0.15-offline','apk':str(dest),'apk_sha256':sha(apk),'apk_bytes':apk.stat().st_size,
        'provider_api_clients_in_apk':False,'internet_permission':False,'runtime_model_download':False,'computer_service_required':False,
        'phone_models':['CREPE-tiny original pretrained MIT','binary-mlp-256-64-11 project trained','Tesseract eng/chi_sim bundled LSTM'],
        'optional_fpga_symbol_inference_preserved':True,'recording_algorithm':'builtin-crepe-pyin-v1',
        'legacy_decoder_retained_and_reused':True,'supported_input':'monophonic voice/humming/instrument; clear printed numeric single-voice jianpu',
        'staff_omr_supported':False,'three_40s_recordings_executed':True,'five_real_score_pages_executed':True,
        'tests':test_counts,'lint_errors':0,'phone_installation_verified':False,'android_webview_verified_on_phone':False,
        'pitch_95_99_percent_claimed':False,'musical_acceptance_passed':False,'sram_written':False,'flash_written':False}
    (OUT/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'使用与验收说明.txt').write_text('''声芯乐动 0.15 · 双识别内置离线版

覆盖安装：包名和0.14相同，签名相同；无需卸载。模型和OCR语言文件随APK提供，首次使用也不下载模型，不需要电脑、网址、API密钥或环境配置。本包面向Android ARM64/ARM32手机。

快速测试：手机开飞行模式，关闭WiFi，打开“创作”。录音成曲→录一段清唱/哼唱/单音乐器或导入音频→选择40秒内片段→识别→试听原声与旋律。图片入口默认“手机内置”，不连接板子也能选择清晰单声部数字简谱并试听；保留可选FPGA符号推理，只有该选项需要连接板子。识别完成后仍可微调、保存、传谱、整段演奏或指引。

本次改动：移除生产APK中的旧联网客户端和INTERNET权限；内置CREPE-tiny神经音高模型与原有经过调试的周期/谐波和事件算法复用，拒绝弱噪声、处理有声短缺口，不让小模型覆盖原来可靠的音高。模型会话复用，不每次重载。正常100ms短音、半音和真实八度跳跃有定向测试。原始时间轴、句间休止、局部重识别、撤销与取消保留。

图片识谱：内置与FPGA相同的17KB定点主符号模型，加本机Tesseract中文/英文OCR和几何结构规则。修复独立降号漏读的通用图形规则；5张现有谱页可在不填参数、无BLE、无非本地网络请求的桌面浏览器中完成。多页导入改为逐页释放非预览位图，避免同时保留6张解码图。曲名、歌词仍可能误识，可在“对照原图微调”修改。当前没有实现五线谱、复杂多声部或任意角度摄影的完整识别。

质量边界：这次完成的是内置部署、流程与回归，并没有达到此前要求的95%—99%识别验收。三首40秒已从源音频运行了真正生产Kotlin路径；没有读取已调好的MIDI或按曲名查答案。与旧v7在旧自动字界上的主音覆盖诊断没有退步，但祖国、牵丝戏仍有偏差。这项诊断不是新算法逐字准确率，节奏和字界还没有独立金标准。试听文件是统一正弦参考音，非FPGA或喇叭录音。

本机测试、Compose渲染、模型/安装包逐项哈希和原生签名通过；真实手机安装、WebView本地OCR、麦克风和蓝牙传谱仍需实测。实际手机分析耗时尚未测量，桌面耗时不能当手机性能。该APK不能被称为音乐质量已验收。FPGA固件和Flash均未修改。之前的网页版服务未随本APK发布，不用旧网址验证这一版离线能力。

开源来源：CREPE/torchcrepe（MIT，原始预训练权重，非本项目训练），Tesseract.js/Tesseract训练数据（Apache-2.0），ONNX Runtime（MIT）。许可证在APK内置assets中。工程训练的MLP只负责数字符号。
https://github.com/maxrmorrison/torchcrepe
https://github.com/marl/crepe
https://github.com/naptha/tesseract.js
https://github.com/microsoft/onnxruntime
''',encoding='utf8')
    hashes={str(p.relative_to(OUT)).replace('\\','/'):sha(p)for p in OUT.rglob('*')if p.is_file()and p.name!='SHA256.json'}
    (OUT/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(release,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
