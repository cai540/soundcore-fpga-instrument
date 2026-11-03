"""Isolate the complete saved-profile/early-pressure headphone experiment."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/early_pressure_20261028/gowin';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'board/soundcore_headphone_60k.gprj'
tree=ET.parse(source)
for item in tree.findall('.//File'):
    path=(source.parent/item.attrib['path']).resolve()
    if path.name=='soundcore_headphone_top.v':path=ROOT/'board/soundcore_early_pressure_top.v'
    item.set('path',path.as_posix())
ET.indent(tree,space='    ')
project=OUT/'soundcore_early_pressure_60k.gprj'
tree.write(project,encoding='utf-8',xml_declaration=True)
(OUT/'build.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module soundcore_early_pressure_top\nrun all\n',encoding='utf-8')
inputs=[project]+[Path(e.attrib['path']) for e in tree.findall('.//File')]
extras=['config/pressure_profile_v1.json','rtl/pressure_profile_config.vh','rtl/pressure_profile_curve.vh']
inputs += [ROOT/name for name in extras]
(OUT.parent/'build_input_sha256.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2),encoding='utf-8')
print(project)
