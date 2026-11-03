"""Evidence-gated changeset release. Does not invoke a programmer or change firmware."""
from pathlib import Path
import hashlib,json,shutil,zipfile,xml.etree.ElementTree as ET,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/independent_note_support_20261101'
OUT=ROOT/'output/independent_note_support_20261101'
JAVA=Path('app/android/app/src/main/java/cn/soundcore/instrument')
TEST=Path('app/android/app/src/test/java/cn/soundcore/instrument')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    log=(BASE/'full.log').read_text(encoding='utf-8',errors='replace')
    assert 'BUILD SUCCESSFUL' in log and 'BUILD FAILED' not in log
    xmls=list((ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST*.xml'))
    suites=[ET.parse(p).getroot() for p in xmls]
    counts={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
    assert counts['tests']>=290 and counts['failures']==counts['errors']==0
    regression=next(s for s in suites if s.get('name','').endswith('NoteSupportRegressionTest'))
    assert regression.get('skipped')=='0'
    actual=[]
    for id in ['zuguo','qiansixi','chilege','demo_voice','demo_twinkle']:
        demo=id.startswith('demo_')
        before=json.loads((BASE/f'baseline/{"heldout" if demo else "real"}/{id}.json').read_text(encoding='utf-8'))['after' if demo else 'production']
        after=json.loads((BASE/f'real/{id}.json').read_text(encoding='utf-8'))['notes']
        fields=['start_ms','duration_ms','midi']
        assert [[r[k] for k in fields] for r in before]==[[r[k] for k in fields] for r in after],id
        actual.append(dict(id=id,notes=len(after),pitch_onset_duration_identical=True,
            weak_evidence_notes=sum(n['confidence']<.5 and n['duration_ms']>=120 for n in after),
            independent_pitch_accuracy_measured=False))
    apk=ROOT/'app/android/app/build/outputs/apk/debug/app-debug.apk'
    old=ROOT/'output/recognition_quality_20261101/声芯乐动_0.18_双识别准确率优化_离线版.apk'
    with zipfile.ZipFile(apk) as z,zipfile.ZipFile(old) as b:
        changed=[n for n in b.namelist() if n.startswith('assets/') and z.read(n)!=b.read(n)]
        assert changed==['assets/models/crepe_tiny.json'],changed
        assert z.read('assets/models/note_support.json')==(ROOT/'app/android/app/src/main/assets/models/note_support.json').read_bytes()
        assert hashlib.sha256(z.read('assets/models/crepe_tiny.onnx')).hexdigest()=='bfd412b7d1b8209bbd2a0ca8f3b96783a7de0ce25cfed4f7d9e9a57595747ccb'
        dex=b''.join(z.read(n) for n in z.namelist() if n.endswith('.dex'))
        assert b'NoteSupportModel' in dex
        assert b'NeuralPitchSequence' not in dex
    lint=(ROOT/'app/android/app/build/reports/lint-results-debug.txt').read_text(encoding='utf-8')
    assert '0 errors' in lint
    source_manifest=(ROOT/'app/android/app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
    assert 'android.permission.INTERNET' not in source_manifest
    manifest=json.loads((BASE/'model/training_manifest.json').read_text(encoding='utf-8'))
    assert manifest['feature_sha256']==sha(BASE/'data/features.jsonl')
    assert manifest['weights_sha256']==sha(BASE/'model/weights.json')
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'声芯乐动_0.19_自主训练音符核对_离线版.apk'
    shutil.copyfile(apk,target)
    report=dict(version='0.19',tests=counts,real_regressions=actual,training=manifest,
        deployment='Android local support/review head; no automatic pitch authority, no FPGA programming',
        rejected_experiment='Automatic veto failed real regression at qiansixi 19330ms; removed without song-specific tuning',
        source_originality='New support head weights trained from random initialization; CREPE/Tesseract remain third-party',
        baseline_assets_changed=changed,crepe_weights_unchanged=True,sheet_assets_unchanged=True,
        network_permission=False,phone_hardware_tested=False,apk_sha256=sha(target),
        lint_summary=re.findall(r'\d+ errors, \d+ warnings',lint)[-1])
    (OUT/'验证结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(ROOT/'docs/自主贡献与第三方来源说明_20261101.md',OUT/'自主贡献与第三方来源说明.md')
    summary=f'''# 0.19 自主训练音符核对版本

录音识别新增从随机权重训练的 225 参数候选音支持模型；在“微调音符与音域”中可定位证据较弱的音。它只提供核对提示，保留 0.18 的自动音高、短音、起止和休止行为。原调音高前端仍是开源 CREPE-tiny，不能将整条流程称为自研基础模型。

Android 共 {counts['tests']} 项测试，{counts['tests']-counts['skipped']} 项通过、{counts['skipped']} 项条件跳过、0 失败。构建与 lint 完成，{report['lint_summary']}。原有五段录音的每个音高、起止和时长均与 0.18 相同；这证明未回退，不能当作它们全部准确。

新模型在独立合成测试的 192 个已知音符窗口中，候选排序命中 191 个；只看神经峰值为 187 个。该结果不包括自动切分，不是真人人声准确率。第一次让模型否决改音曾造成一处回退，已保留失败证据并撤下其自动决策权；真实人声训练和校准仍待完成。

本轮未更改 FPGA 固件或烧录，也未发布网页、调用 API。原简谱引擎、数字分类器权重和 CREPE 权重均保留。只纠正了 CREPE 元数据中的 hop：神经观察 320 个采样、声学观察 160 个采样，原来元数据误混为 160。

`本轮源码与训练证据.zip` 是变更及训练证据包，不是独立可编译的完整工程。含生成脚本、逐条训练特征、划分清单、权重、测试及失败记录；合成原始 PCM 可由脚本重新生成。阅读 `自主贡献与第三方来源说明.md` 查看每部分可采用的准确表述。
'''
    (OUT/'本轮说明.md').write_text(summary,encoding='utf-8')
    snapshots=ROOT/'app/android/app/build/reports/paparazzi/debug'
    runs=[p for p in (snapshots/'runs').glob('*.js') if '#melodyResult' in p.read_text(encoding='utf-8')]
    run=max(runs)
    image_record=json.loads(re.search(r'=\s*(\[.*\]);',run.read_text(encoding='utf-8'),re.S).group(1))[0]
    screenshot=OUT/'录音核对页面.png'
    shutil.copyfile(snapshots/image_record['file'],screenshot)
    sources=[JAVA/n for n in ['NoteSupportEvidence.kt','NoteSupportModel.kt','AcousticNoteConsensus.kt','BuiltinMelodyRecognition.kt','MelodyPanel.kt']]
    sources += [TEST/n for n in ['NoteSupportModelTest.kt','NoteSupportDatasetTest.kt','NoteSupportRegressionTest.kt','AcousticNoteConsensusTest.kt']]
    sources += [Path('scripts')/n for n in ['generate_note_support_data.py','train_note_support.py','release_note_support_20261101.py','prepare_builtin_recognition_20261101.py']]
    sources += [Path('app/android/app/build.gradle.kts'),Path('app/android/app/src/test/resources/note_support_vectors.json'),
        Path('app/android/app/src/main/assets/models/note_support.json'),Path('app/android/app/src/main/assets/models/crepe_tiny.json'),
        Path('docs/自主贡献与第三方来源说明_20261101.md'),Path('docs/plans/2026-11-01-independent-note-support.md')]
    sources += [p.relative_to(ROOT) for p in (ROOT/'app/android/app/src/main/assets/open_source_licenses').glob('*') if p.is_file()]
    evidence=[BASE/'data/manifest.json',BASE/'data/features.jsonl',BASE/'model/weights.json',BASE/'model/training_manifest.json',BASE/'dataset.log',BASE/'full.log']
    evidence += list((BASE/'real').glob('*.json'))+list((BASE/'rejected_automatic_veto').glob('*'))+xmls
    with zipfile.ZipFile(OUT/'本轮源码与训练证据.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sources:z.write(ROOT/p,str(p).replace('\\','/'))
        for p in evidence:z.write(p,str(p.relative_to(ROOT)).replace('\\','/'))
        for p in [OUT/'验证结果.json',OUT/'本轮说明.md',screenshot]:z.write(p,p.name)
    print(json.dumps(dict(output=str(OUT),tests=counts,apk_sha256=report['apk_sha256'],real=actual),ensure_ascii=False))

if __name__=='__main__':main()
