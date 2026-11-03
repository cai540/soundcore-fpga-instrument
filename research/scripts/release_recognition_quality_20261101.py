"""Package measured offline recognition changes; no device writes or provider calls."""
from pathlib import Path
import hashlib,json,shutil,subprocess,os,csv,html,zipfile,xml.etree.ElementTree as ET,sys
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'build/recognition_quality_20261101';O=R/'output/recognition_quality_20261101'
sys.path.insert(0,str(R/'evaluation/transcription'))
from character_metrics import compare
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
def align(gold,pred):
    n=len(gold);m=len(pred);d=[[0]*(m+1)for _ in range(n+1)]
    for i in range(n+1):d[i][0]=i
    for j in range(m+1):d[0][j]=j
    for i in range(1,n+1):
        for j in range(1,m+1):d[i][j]=min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(gold[i-1]!=pred[j-1]['degree']))
    pairs=[];i=n;j=m;extra=missing=0
    while i or j:
        if i and j and d[i][j]==d[i-1][j-1]+(gold[i-1]!=pred[j-1]['degree']):i-=1;j-=1;pairs.append((i,j))
        elif j and d[i][j]==d[i][j-1]+1:j-=1;extra+=1
        else:i-=1;missing+=1
    return pairs,extra,missing
def sheet_metrics():
    gold=json.loads((R/'build/sheet_acceptance_20261031/manual_first_rows.json').read_text(encoding='utf8'))['samples'];result={}
    for stage in ['before','after']:
        rows=[]
        for row in json.loads((B/stage/'sheet_symbol_quality.json').read_text(encoding='utf8')):
            g=gold[row['id']];pred=[x for x in row['raw'].get('row',[])if 0<=x['degree']<=7]
            pairs,extra,missing=align(g['degree'],pred)
            exact=sum(pred[j]['degree']==g['degree'][i]and pred[j]['octave']==g['octave'][i]and pred[j]['ticks']==g['ticks'][i]for i,j in pairs)
            rows.append({'id':row['id'],'variant':row['variant'],'flow_completed':row['ok'],'reference_notes':len(g['degree']),
                'confirmed_notes':len(pred),'exact_degree_octave_duration':exact,'extra':extra,'missing':missing})
        result[stage]={'cases':rows,'clean_reference':sum(x['reference_notes']for x in rows if x['variant']=='clean'),
            'clean_exact':sum(x['exact_degree_octave_duration']for x in rows if x['variant']=='clean'),
            'all_reference':sum(x['reference_notes']for x in rows),'all_exact':sum(x['exact_degree_octave_duration']for x in rows),
            'completed_cases':sum(x['flow_completed']for x in rows)}
    return result
def audio_metrics():
    reference=json.loads((R/'evaluation/transcription/character_reference40_audited.json').read_text(encoding='utf8'));rows=[]
    for c in reference['cases']:
        ident=c['id'];old=json.loads((B/f'before/{ident}.json').read_text(encoding='utf8'))['projected'];new=json.loads((B/f'after/{ident}.json').read_text(encoding='utf8'))['production']
        gold=[u for p in c['phrases']for u in p['units']];spans=json.loads((R/f'output/vocal_units40_20261030/{ident}/characters.json').read_text(encoding='utf8'))['units'];row={'id':ident}
        for label,notes in [('before',old),('after',new)]:
            good=0;issues=[]
            for i,(g,u)in enumerate(zip(gold,spans)):
                a=u['notes'][0]['start_ms'];z=u['notes'][-1]['end_ms'];weights={}
                for note in notes:
                    overlap=max(0,min(z,note['start_ms']+note['duration_ms'])-max(a,note['start_ms']))
                    weights[note['midi']]=weights.get(note['midi'],0)+overlap
                best=max(weights,key=weights.get)if weights and max(weights.values())>0 else None
                ok=any(best in allowed for allowed in g['allowed_sequences']);good+=ok
                if not ok:issues.append({'index':i,'character':g['character'],'allowed':g['allowed_sequences'],'dominant':best})
            seq=compare(gold,[n['midi']for n in notes]);seq.pop('path')
            row[label]={'dominant_pitch_coverage_on_OLD_AUTOMATIC_spans':good,'reference_units':len(gold),'notes':len(notes),'sequence_diagnostic':seq,'remaining_issues':issues}
        old_by_time={(n['start_ms'],n['duration_ms']):n for n in old}
        row['changed_labels']=[{'time_ms':n['start_ms'],'before':old_by_time[n['start_ms'],n['duration_ms']]['midi'],'after':n['midi']}for n in new if (n['start_ms'],n['duration_ms'])in old_by_time and old_by_time[n['start_ms'],n['duration_ms']]['midi']!=n['midi']]
        new_times={(n['start_ms'],n['duration_ms'])for n in new};row['rejected_unsupported_notes']=[n for n in old if (n['start_ms'],n['duration_ms'])not in new_times]
        assert row['after']['dominant_pitch_coverage_on_OLD_AUTOMATIC_spans']>=row['before']['dominant_pitch_coverage_on_OLD_AUTOMATIC_spans']
        rows.append(row)
    return {'independent_word_timing_gold':False,'rhythm_accuracy_measured':False,'whole_song_accuracy_claimed':False,'musical_acceptance_passed':False,'cases':rows}
def previews():
    folder=O/'试听';folder.mkdir(exist_ok=True);titles={'zuguo':'我和我的祖国','qiansixi':'牵丝戏','chilege':'敕勒歌'}
    files=[]
    for ident,title in titles.items():
        pcm=np.fromfile(R/f'build/builtin_recognition_20261101/{ident}.f32',dtype='<f4');wave=np.zeros_like(pcm);phase=0.0
        notes=json.loads((B/f'after/{ident}.json').read_text(encoding='utf8'))['production']
        for n in notes:
            a=n['start_ms']*16;z=min(len(pcm),(n['start_ms']+n['duration_ms'])*16);length=z-a
            t=np.arange(length)/16000;omega=2*np.pi*440*2**((n['midi']-69)/12)
            envelope=np.minimum(1,t/.012)*np.minimum(1,(length-1-np.arange(length))/16000/.018)
            wave[a:z]=.22*np.sin(phase+omega*t)*envelope;phase=(phase+omega*length/16000)%(2*np.pi)
        reference=pcm*.8/max(.8,float(abs(pcm).max()))
        for label,data in [('参考旋律',wave),('原声左_旋律右',np.column_stack([reference,wave]))]:
            path=folder/f'{title}_{label}_40秒.mp3';channels=1 if data.ndim==1 else 2
            subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','16000','-ac',str(channels),'-i','pipe:0','-c:a','libmp3lame','-q:a','2',str(path)],input=data.astype('<f4').tobytes(),check=True)
            decoded=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ar','16000','-ac',str(channels),'-f','f32le','-']),dtype='<f4')
            assert decoded.size==data.size and np.isfinite(decoded).all()and abs(decoded).max()<.999
            files.append({'id':ident,'title':title,'label':label,'path':path.relative_to(O).as_posix(),'seconds':40})
    return files
def main():
    assert 'BUILD SUCCESSFUL'in (B/'android_checks.log').read_text(encoding='utf8')
    assert 'fail 0'in (B/'js_tests.log').read_text(encoding='utf8')
    tests=[ET.parse(p).getroot()for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
    counts={k:sum(int(t.get(k,'0'))for t in tests)for k in ['tests','failures','errors','skipped']}
    assert counts['tests']>=285 and counts['failures']==counts['errors']==0
    lint=ET.parse(R/'app/android/app/build/reports/lint-results-debug.xml').getroot();assert not [x for x in lint.findall('issue')if x.get('severity')in ['Error','Fatal']]
    runtime=json.loads((B/'packaged/sheet_validation.json').read_text(encoding='utf8'));assert not runtime['non_local_requests']
    assert runtime['results'][0]['new_language_loads']==2 and all(x['new_language_loads']==0 for x in runtime['results'][1:])
    retry=json.loads((B/'packaged/cancel_retry.json').read_text());assert retry=={'ids':[91],'error':None,'complete':True}
    heldout=[]
    for ident in ['demo_voice','demo_twinkle']:
        row=json.loads((B/f'heldout/{ident}.json').read_text(encoding='utf8'));assert row['before']==row['after']
        heldout.append({'id':ident,'notes':len(row['after']),'unchanged_pitches_timing_count':True,'independent_accuracy_gold':False})
    apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk';sdk=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0');os.environ['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
    badging=subprocess.check_output([str(sdk/'aapt2.exe'),'dump','badging',str(apk)]).decode('utf8');assert "versionCode='18'"in badging and 'android.permission.INTERNET'not in badging
    cert=subprocess.check_output([str(sdk/'apksigner.bat'),'verify','--print-certs',str(apk)]).decode()
    assert 'd6d6a066cddaf6267acf014430bf0dd3e12ce0027f6a4a055c3bcdde5f320abc'in cert
    assets=R/'app/android/app/src/main/assets'
    with zipfile.ZipFile(apk)as z:
        for folder in ['offline','models','open_source_licenses']:
            for p in (assets/folder).rglob('*'):
                if p.is_file():assert z.read('assets/'+p.relative_to(assets).as_posix())==p.read_bytes()
        dex=b''.join(z.read(p)for p in z.namelist()if p.endswith('.dex'))
        for forbidden in ['dashscope.aliyuncs.com','trycloudflare.com','ScoreApiClient','ManagedRecognition','ScoreApiSettings','NeuralPitchSequence']:
            assert forbidden.encode()not in dex and forbidden.encode('utf-16le')not in dex,forbidden
    assert sha(assets/'models/crepe_tiny.onnx')=='bfd412b7d1b8209bbd2a0ca8f3b96783a7de0ce25cfed4f7d9e9a57595747ccb'
    frozen=json.loads((R/'build/low_latency_20261101/build_metadata.json').read_text(encoding='utf8'))
    assert all(sha(Path(x['origin']))==x['sha256']for x in frozen['source_records']),'FPGA sources changed'
    O.mkdir(exist_ok=True);app=O/'声芯乐动_0.18_双识别准确率优化_离线版.apk';copy(apk,app)
    sheet=sheet_metrics();audio=audio_metrics();samples=previews()
    assert sheet['after']['clean_exact']==sheet['after']['clean_reference']==103
    assert sheet['after']['all_exact']>=400
    report={'version':18,'algorithm':'builtin-crepe-acoustic-consensus-v2','algorithm_version':9,'android':counts,'js_tests':42,
        'sheet':sheet,'audio':audio,'heldout_regressions':heldout,'runtime':runtime,'cancel_retry':retry,'audio_previews':samples,
        'same_signing_certificate':True,'no_internet_permission':True,'runtime_external_api_calls':0,'models_unchanged':True,
        'fpga_firmware_unchanged':'9422','sram_written':False,'flash_written':False,'phone_installation_verified':False,
        'musical_acceptance_passed':False,'apk_sha256':sha(app),'apk_bytes':app.stat().st_size}
    (O/'验证结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ['android_checks.log','js_tests.log','audio_ablation.log','targeted_audio.log','heldout.log','packaged_sheet.log']:
        if(B/name).exists():copy(B/name,O/'evidence'/name)
    for folder in ['before','after','packaged','heldout']:
        for p in (B/folder).glob('*.json'):copy(p,O/'evidence'/folder/p.name)
    for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):copy(p,O/'evidence/android'/p.name)
    baseline=json.loads((B/'baseline.json').read_text(encoding='utf8'))['files'];changed=[]
    for directory in ['app/android/app/src/main/java','app/android/app/src/test/java','web/phone-lab-20261030/lib','web/phone-lab-20261030/tests']:
        for p in (R/directory).rglob('*'):
            if p.is_file()and baseline.get(p.relative_to(R).as_posix())!=sha(p):changed.append(p)
    changed.extend([R/'app/android/app/build.gradle.kts',R/'docs/plans/2026-11-01-recognition-quality.md',Path(__file__),R/'scripts/audit_sheet_quality_20261101.cjs',R/'scripts/check_quality_sheet_runtime_20261101.cjs'])
    for p in changed:copy(p,O/'source'/p.relative_to(R))
    write_report(report)
    archive=O/'本轮源码与验证.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
        for directory in ['source','evidence']:
            for p in (O/directory).rglob('*'):
                if p.is_file():z.write(p,p.relative_to(O).as_posix())
        z.write(O/'验证结果.json','验证结果.json');z.write(O/'改动与边界.md','改动与边界.md')
    print(json.dumps({'apk':str(app),'android':counts,'clean_sheet':[sheet['after']['clean_exact'],103],
        'augmented_sheet':[sheet['after']['all_exact'],sheet['after']['all_reference']],
        'before_augmented':sheet['before']['all_exact'],'heldout':heldout,'changed_files':len(changed)},ensure_ascii=False,indent=2))

def write_report(m):
    s=m['sheet'];audio=m['audio']['cases'];names={'zuguo':'我和我的祖国','qiansixi':'牵丝戏','chilege':'敕勒歌'}
    text=f'''# 双识别优化候选 0.18

本轮更新手机内置算法、模型调用和图像处理，保留0.17的低延迟蓝牙调度。未更新或烧录FPGA，继续配套9422；引脚不变。APK签名不变，可覆盖安装，没有INTERNET权限、API客户端或运行时模型下载。

## 已修复

1. 图片变暗后数字变成未知类、低对比度整页分行失败：统一灰度/透明背景处理和按图像分布归一化。轻微倾斜自动校正；几何读线和模型裁图使用同一坐标，避免校正后裁错位置。
2. “6”等细笔画被模型拒识：只对低置信度主符号做多阈值复核，仍使用原有手机/FPGA同权重模型；不按小节拍数猜数字。无法确认的符号保留待核对状态。
3. 弧线碎片被当作高八度点、细线碎片被当作附点：增加像素连通性核查，保留真正孤立的点。
4. 多页图片同时留在内存：改为逐页处理，处理完上一页再载入下一页。未测手机峰值内存，不能把代码改动说成实测RAM下降。
5. 每次识谱都重新载入OCR：完成任务后保留两种语言工作器。桌面本地测试中首次加载2份语言文件，之后3个任务没有重载；同一图片再次识别约0.2秒，这包含缓存，不能当新图片或手机的耗时。
6. 录音微弱或含直流偏置时失去有声判定：只对分析副本去偏置、限幅度增益，原声回放不改；正常输入直接原样通过。实际ONNX推理的弱音/DC、白噪声、半音、100ms短音、真实八度跳跃与模型复用测试通过。
7. 原事件标签与声学/神经证据冲突：双方持续支持替代音高时才修改标签；两种证据都不支持的短恢复音被拒绝。保留所有有支持的正常音和原始时值，不靠吞短音减少碎音。

直接提高神经模型权重的序列解码会增加碎音并使《我和我的祖国》变差，因此只留在测试研究代码，未进入APK。没有按曲名、歌词、特定秒数或旧成品谱修正运行结果。

## 可复查结果

- 五张原谱的第一行，人工标注共103音（包括休止）：数字、八度、时值同时正确从{s['before']['clean_exact']}/103到{s['after']['clean_exact']}/103。
- 同样五张图增加暗图、低对比度和1.5°倾斜，共20个固定测试：分行/主符号流程完成{s['before']['completed_cases']}/20→{s['after']['completed_cases']}/20；三项同时正确从{s['before']['all_exact']}/{s['before']['all_reference']}到{s['after']['all_exact']}/{s['after']['all_reference']}。这是重复增强后的固定样本，只有5张独立图片；不是任意曲谱的识别准确率，更不代表后续所有谱行正确。
- 真正打包的OCR/整数模型在桌面浏览器完成5页、多页串联、重复任务和取消后重试；无非本地请求、无蓝牙调用。最新JSON另经过真实Kotlin编译、分段及容量检查。并非真实手机WebView或FPGA实测。
- Android {m['android']['tests']-m['android']['skipped']}项通过，{m['android']['skipped']}项跳过，零失败；JS {m['js_tests']}项通过；APK构建、lint和签名/资产核查通过。

录音开发诊断使用旧自动字界上的主要音高重叠覆盖，时间边界不是独立人工金标准。不能称为逐字准确率、节奏准确率、整曲准确率，亦未达到之前95%/99%的整体验收：

| 40秒片段 | 旧覆盖 | 新覆盖 | 原/新输出音数 |
|---|---:|---:|---:|
'''
    for row in audio:text+=f"| {names[row['id']]} | {row['before']['dominant_pitch_coverage_on_OLD_AUTOMATIC_spans']}/{row['before']['reference_units']} | {row['after']['dominant_pitch_coverage_on_OLD_AUTOMATIC_spans']}/{row['after']['reference_units']} | {row['before']['notes']}/{row['after']['notes']} |\n"
    text+='''
《牵丝戏》两处标签得到纠正；《我和我的祖国》句间一枚150ms、pYIN仅约0.02且对应神经标签证据很低的音被剔除。其余保留音的时值不变。《两只老虎》30秒、《小星星》35.8秒作为额外回归，音高、时值和数量与0.17完全一致，但没有独立逐音金标准，不能宣称它们100%准确。

## 仍有问题

祖国的“一”等位置仍有八度/音高偏差；牵丝戏部分弱音、装饰音与字界仍不稳定。提高模型权重并不能解决这些问题。识谱增强测试尚有一处无法确认的主符号；罕见曲名字形仍可能读错，例如“敕”读成“救”。全页剩余谱行、实际拍摄透视、阴影、多声部与五线谱均没有在本轮取得完整准确率验收。

录音时长/节奏尚缺独立人工标注，未计算节奏准确率。没有以测试通过、流程能完成或少量样本高分代替音乐验收。手机安装、麦克风环境、WebView耗时和真实FPGA传谱仍待实测。

## 试听与复现

“试听”中的文件来自实际生产Kotlin输出；统一正弦参考音用于核对音高、节奏及停顿，不代表口琴/二胡音色或实机录音。“原声左_旋律右”方便耳机对照。原始40秒时钟保留。

工作区：Android项目在app/android，用现有JDK17/Android SDK执行Gradle testDebugUnitTest assembleDebug lintDebug。设置SOUNDCORE_RECOGNITION_AUDIT=1及SOUNDCORE_AUDIT_STAGE=after可导出真实三首音频的观察与生产结果；SOUNDCORE_RECOGNITION_HELDOUT=1运行两份额外素材回归。JS运行node --test tests/*.test.mjs；scripts/audit_sheet_quality_20261101.cjs运行符号对照；scripts/check_quality_sheet_runtime_20261101.cjs运行已打包识谱与取消/重试检查。

本轮未发布到旧网页版地址。请以本APK及本报告附件为准。源码和证据ZIP是本轮变更集，完整Android工程仍在工作区，未重复打包不变的大模型。

参考原理：[torchcrepe官方解码说明](https://github.com/maxrmorrison/torchcrepe)、[librosa官方pYIN说明](https://librosa.org/doc/main/generated/librosa.pyin.html)。神经模型使用原始CREPE-tiny权重，未宣称由本项目重新训练；整数主符号模型权重保持与9422一致。
'''
    (O/'改动与边界.md').write_text(text,encoding='utf8')
    players=''.join(f'<article><h3>{names[row["id"]]}</h3><audio controls preload="metadata" src="{html.escape(next(a["path"]for a in m["audio_previews"]if a["id"]==row["id"]and a["label"]=="原声左_旋律右"),quote=True)}"></audio><p>左声道原人声，右声道算法参考音；40秒。</p></article>'for row in audio)
    page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声芯乐动 · 双识别验证0.18</title><style>body{{margin:0;background:#091723;color:#e5f0ef;font:16px/1.8 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:36px 22px}}h1{{line-height:1.3}}.tag{{color:#50dec7}}article{{padding:20px;margin:18px 0;background:#142b38;border:1px solid #2b4b58;border-radius:18px}}audio{{width:100%}}a{{color:#50dec7}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;font:inherit}}.notice{{color:#f0c681}}</style><main><p class="tag">SOUNDCORE / 0.18 / OFFLINE</p><h1>双识别：改动、证据与试听</h1><p>五张清晰谱页首行103/103；20种固定图像条件{s['after']['all_exact']}/{s['after']['all_reference']}。<br>范围仅限所列首行，不是整个功能或任意图片的准确率。</p><p class="notice">录音仍未达到95%—99%的整体验收。下面提供真实输出，保留剩余问题。</p>{players}<p><a href="改动与边界.md">详细报告</a> · <a href="验证结果.json">机器可读验证结果</a></p><details><summary>查看完整说明</summary><pre>{html.escape(text)}</pre></details></main></html>'''
    (O/'对照试听与验证.html').write_text(page,encoding='utf8')

if __name__=='__main__':main()
