from pathlib import Path
import json,hashlib,shutil
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
import fitz

ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/shared_pitch_20261028';OUT=ROOT/'output/shared_pitch_20261028'
data=json.loads((BUILD/'release.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(Path(data['firmware']))==data['sha256']
assert not data['sram_written'] and not data['flash_written']
assert data['resources']['DSP']['used']==45.5
checks={}
for folder,name,pages in [('report','声芯_竞赛技术文档_共享流水线实证版',13),('results','共享音高流水线_优化结果',3)]:
    pdf=OUT/folder/(name+'.pdf');docx=pdf.with_suffix('.docx')
    with fitz.open(pdf) as doc:
        assert len(doc)==pages
        txt=''.join(p.get_text() for p in doc)
        assert '\ufffd' not in txt
        for token in ['C2B3','193','57.7','45.5']:assert token in txt,token
    render=json.loads((pdf.parent/'render_validation.json').read_text(encoding='utf-8'))
    assert not render['overflow']
    with ZipFile(docx) as z:
        xml=E.fromstring(z.read('word/document.xml'))
        text=''.join(xml.xpath('//w:t/text()',namespaces={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}))
        assert not any(token in text for token in ['浙江大学','Lwc01','wxid_'])
    checks[folder]={'pages':pages,'text_and_overflow_check':True,'visually_reviewed':True}
protected=json.loads((BUILD/'baseline/protected.json').read_text())
for name,expected in protected.items():assert sha(ROOT/name)==expected
quality=OUT/'quality';quality.mkdir(exist_ok=True)
qa={'document_checks':checks,'regression_tests':len(data['tests']),
 'all_regressions_passed':all(t['passed'] for t in data['tests']),
 'baseline_tests_passed':len(data['baseline_tests_after_testbench_corrections']),
 'code_review':{'scope':'Only product change is playable_synth32; arithmetic width/truncation, frame semantics, reset and 256-clock deadline reviewed.',
                'actionable_product_findings':[],
                'testbench_corrections':'Two old audition checks fixed and checked against legacy and shared variants.',
                'not_performed':'Physical listening, analog FFT and measured sensor-to-audio latency'},
 'protected_files_unchanged':len(protected),'firmware':data['user_code'],
 'sram_written':False,'flash_written':False}
(quality/'final_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
readme='''# 共享音高流水线优化交付

当前候选0xC2B3已完成构建，未烧录SRAM或Flash。当前板上已知基线是此前0x9D67。

先看results/共享音高流水线_优化结果.pdf，再看report中的竞赛技术文档PDF/Word。
DSP107.5→45.5、Logic30280→26990、寄存器9614→11111、BSRAM45不变。
保留32声部、名义48kHz；193/256拍内完成。11项检查通过。
动态对照使用同帧快照语义，不宣称任意时刻读参都和旧实现等价。

firmware包含完整耳机候选位流。evidence保留实际资源/时序/管脚报告、发布记录和通过日志。
source保留本次改动及生成检查工具；baseline_reference保留原版源码以便重现比较。
本包没有修改或重新生成APK，也没有改变两首曲库。电源整改、实板听感、模拟频谱和端到端延迟仍待验收。

此包是同一工作区的版本快照，部分工程及曲库引用为原工作区绝对路径；若迁移到其他电脑，需要先修正路径，不能仅换一个目录直接保证构建。
'''
(OUT/'使用说明.md').write_text(readme,encoding='utf-8')
archive=OUT/'声芯_共享流水线优化交付包_2026-10-28.zip'
members={}
for folder in ['report','results','quality']:
    for p in (OUT/folder).rglob('*'):
        if p.is_file() and 'rendered' not in p.parts and p.name!='sha256_manifest.json':members[str(p.relative_to(OUT))]=p
members['使用说明.md']=OUT/'使用说明.md'
members['firmware/'+Path(data['firmware']).name]=Path(data['firmware'])
for name in ['release.json','all_tests.json','baseline_all_tests.json','resource_report.txt','timing_report.html','pin_report.html','gowin_build.log']:
    members['evidence/'+name]=BUILD/name
for t in data['tests']:members['evidence/'+t['test']+'.log']=BUILD/(t['test']+'.log')
for t in data['baseline_tests_after_testbench_corrections']:
    name='baseline_'+t['test']+'.log';members['evidence/'+name]=BUILD/name
for p in (BUILD/'baseline').rglob('*'):
    if p.is_file():members['baseline_reference/'+str(p.relative_to(BUILD/'baseline'))]=p
for rel in data['source_sha256']:
    p=ROOT/rel;members['source/'+rel]=p
for name in ['tb_shared_pitch_snapshot.v','tb_shared_pitch_equivalence.v','tb_playable_synth32.v','tb_pressure_i2s_poly32_core.v']:
    members['source/tb/'+name]=ROOT/'tb'/name
for name in ['check_shared_pitch.py','prepare_shared_pitch_build.py','finalize_shared_pitch.py','report_shared_pitch_results.py','check_organic_build.py']:
    members['source/scripts/'+name]=ROOT/'scripts'/name
members={name.replace('\\','/'):path for name,path in members.items()}
hashes={name:sha(path) for name,path in members.items()}
(quality/'sha256_manifest.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
members['quality/sha256_manifest.json']=quality/'sha256_manifest.json'
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for name,p in members.items():z.write(p,name)
with ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'package':str(archive),'bytes':archive.stat().st_size,'documents':checks,'regressions':len(data['tests'])},ensure_ascii=False,indent=2))
