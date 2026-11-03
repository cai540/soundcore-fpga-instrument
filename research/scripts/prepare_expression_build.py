from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/expression_20261028';GOWIN=OUT/'gowin_rom';GOWIN.mkdir(exist_ok=True)
source=ROOT/'build/early_pressure_20261028/gowin/soundcore_early_pressure_60k.gprj'
tree=ET.parse(source)
for item in tree.findall('.//File'):
    if Path(item.attrib['path']).name=='soundcore_early_pressure_top.v':item.set('path',(ROOT/'board/soundcore_expression_top.v').as_posix())
for name in ['rtl/pressure_expression32.v','rtl/expressive_texture.v']:
    ET.SubElement(tree.find('FileList'),'File',path=(ROOT/name).as_posix(),type='file.verilog',enable='1')
ET.indent(tree,space='    ');project=GOWIN/'soundcore_expression_60k.gprj'
tree.write(project,encoding='utf-8',xml_declaration=True)
(GOWIN/'build.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module soundcore_expression_top\nrun all\n')
inputs=[project]+[Path(e.attrib['path']) for e in tree.findall('.//File')]
inputs += [ROOT/'config/expression_profile_v1.json',ROOT/'config/pressure_profile_v1.json']
inputs += [ROOT/'rtl/expression_normalized.mem',ROOT/'rtl/expression_raw.mem']
(OUT/'build_input_sha256.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2))
print(project)
