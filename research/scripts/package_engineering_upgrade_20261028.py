from pathlib import Path
import json,csv,hashlib,shutil,re
from zipfile import ZipFile,ZIP_DEFLATED
import fitz
from PIL import Image,ImageDraw,ImageFont
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/engineering_upgrade_20261028'
readme='''# 声芯：工程图与技术改进设计包

本包不改变当前固件、APK或曲目。主报告保留竞赛模板五部分；新增研究尚待实现及对照验证。

## 建议阅读顺序
1. proposal/声芯_技术创新与资源优化方案.pdf：三路线取舍、资源热点、共享流水及早期力度试验。
2. report/声芯_竞赛技术文档_工程图修订版.pdf / .docx：模板试填修订版，现有成果与未来方案分别标明。
3. schematics/声芯_模块级电路原理图_RevA.pdf：五张A3矢量图，按购买模块的外部接口绘制。
4. cad/声芯_三维装配视图.pdf：装配、分解和移除侧板后的内部模块包络。

## 电路图的范围
包含七路4.7k/FSR/10k分压、滑杆、七颗1k限流LED、五颗常开键、OLED、JDY载板、MAX外放、EC11及可选K5灯环驱动。
第1页单入口分配是候选：总12V在面包板前分支，一路接FPGA原DC入口，一路经合格降压给外设。
新电源已购买，其型号、额定电流、温升与实际接线还需核对。不能把面包板3.3V/5V输出当作FPGA通用电源输入。
同名网表示电气相连。electrical_netlist.json及connections.csv是连接清单；SVG可编辑。
这些不是KiCad原生工程，尚未执行EDA的ERC/DRC；模块内部未知电路没有猜画。

## 三维文件的范围
STEP：包含50个有效实体，可导入FreeCAD等支持STEP的软件；STL和GLB用于网格/展示。
parameters.json记录主要假设尺寸；三维源程序包含各模块和控件的坐标及尺寸，可据实测修改。
机身420×240×80mm、板厚3mm、各板卡包络、孔径、孔距均是规划占位，不是照片实测。
已有敲击面在模型中只用外包络表示，没有重新设计其传感结构。
内部灰色块是安装净空，不代表真实电子元件外形。内部视图移除了前/右侧板，便于观察。
尚未校准到手五键、真实板卡孔位、连接器插拔空间、线束弯曲半径、散热及公差，不可直接加工。
旧聊天中的临时照片当前不可读取；本次未运行照片重建，未把AI网格当作工程尺寸依据。

## 可追溯性
resource_audit/audit.json为当前发布基线与源码核对；hierarchy_resources.csv为层次报告解析。
当前DSP107.5/118；新增共享音高目标未实装，无优化后节省量。综合DSP运算实例不等于物理DSP报告单位。
源文件在sources/中保留；源程序是生成/分析工具，不是新的乐器固件。
quality/final_qa.json记录文档、网名覆盖、CAD几何、哈希及渲染检查。
'''
(OUT/'使用说明.md').write_text(readme,encoding='utf-8')
net=json.loads((OUT/'schematics/electrical_netlist.json').read_text(encoding='utf-8'))
for name,rows in [('connections',net['connections']),('components',net['components'])]:
    with (OUT/f'schematics/{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
pdf=fitz.open()
for n in ['assembly','exploded','inside']:
    page=pdf.new_page(width=841.89,height=595.28)
    page.insert_image(fitz.Rect(5,8,836.89,587.28),filename=str(OUT/f'cad/{n}.png'),keep_proportion=True)
pdf.save(OUT/'cad/声芯_三维装配视图.pdf',garbage=4,deflate=True);pdf.close()

srcdir=OUT/'sources';srcdir.mkdir(exist_ok=True)
for s in ['build_engineering_cad_20261028.py','build_module_schematics_20261028.py','audit_resources_for_report_20261028.py',
          'revise_engineering_documents_20261028.py','fill_contest_technical_document_20261028.py','render_engineering_docs_20261028.py']:
    shutil.copy2(ROOT/'scripts'/s,srcdir/s)
shutil.copy2(ROOT/'docs/plans/2026-10-28-technical-innovation-design.md',OUT/'proposal/技术创新设计记录.md')

quality=OUT/'quality';quality.mkdir(exist_ok=True)
resource=json.loads((OUT/'resource_audit/audit.json').read_text(encoding='utf-8'))
cad=json.loads((OUT/'cad/cad_validation.json').read_text(encoding='utf-8'))
sch=json.loads((OUT/'schematics/schematic_validation.json').read_text(encoding='utf-8'))
checks={}
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
for folder,name,table_count in [('report','声芯_竞赛技术文档_工程图修订版',6),('proposal','声芯_技术创新与资源优化方案',7)]:
    path=OUT/f'{folder}/{name}.docx'
    with ZipFile(path) as z:
        xml=E.fromstring(z.read('word/document.xml'));txt=''.join(xml.xpath('//w:t/text()',namespaces=ns))
        assert len(xml.findall('.//w:tbl',ns))==table_count
        assert all(term not in txt for term in ['浙江大学','Lwc01','wxid_','全球首创'])
    with fitz.open(path.with_suffix('.pdf')) as d:
        alltxt=''.join(p.get_text() for p in d);assert '\ufffd' not in alltxt
        assert len(d)==json.loads((path.parent/'render_validation.json').read_text(encoding='utf-8'))['word_pages']
        pages=len(d)
    checks[folder]={'pages':pages,'tables':table_count,'pdf_nonempty':True,'text_anonymity_check':True,
      'overflow':json.loads((path.parent/'render_validation.json').read_text(encoding='utf-8'))['overflow']}
    assert not checks[folder]['overflow']
with fitz.open(OUT/'schematics/声芯_模块级电路原理图_RevA.pdf') as d:
    assert len(d)==5
    assert all(p.rect.width>1100 and p.rect.height>800 for p in d)
qa={'documents':checks,'schematic':sch,
    'cad':{k:v for k,v in cad.items() if k!='parts_list'},
    'firmware_unchanged':resource['baseline']['firmware_matches_release'],
    'source_release_input_hashes_match':all(x['match'] for x in resource['source_input_hashes'].values()),
    'new_algorithms_implemented':False,'photo_reconstruction_performed':False,
    'render_visual_review':'All pages reviewed as contact sheets; engineering figure and resource pages inspected at readable resolution.',
    'word_limit_check':json.loads((OUT/'report/document_validation.json').read_text(encoding='utf-8'))['limited_sections']}
assert qa['firmware_unchanged'] and qa['source_release_input_hashes_match']
(quality/'final_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={}
for p in OUT.rglob('*'):
    if p.is_file() and p.suffix.lower() not in ['.zip'] and 'rendered' not in p.parts:
        manifest[str(p.relative_to(OUT))]=hashlib.sha256(p.read_bytes()).hexdigest()
(quality/'sha256_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=OUT/'声芯_技术方案与工程图包_2026-10-28.zip'
with ZipFile(archive,'w',ZIP_DEFLATED) as z:
    for p in OUT.rglob('*'):
        if p.is_file() and p!=archive and 'rendered' not in p.parts:
            z.write(p,str(p.relative_to(OUT)))
print(json.dumps({'archive':str(archive),'archive_bytes':archive.stat().st_size,'checks':checks,
 'schematic_sheets':sch['sheets'],'cad_solids':cad['step_solid_count']},ensure_ascii=False,indent=2))
