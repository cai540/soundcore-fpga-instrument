"""Create an isolated full-product Gowin build, preserving board/impl."""
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/shared_pitch_20261028/gowin';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'board/soundcore_headphone_60k.gprj'
tree=ET.parse(source)
for item in tree.findall('.//File'):
    item.set('path',(source.parent/item.attrib['path']).resolve().as_posix())
ET.indent(tree,space='    ')
project=OUT/'soundcore_shared_pitch_60k.gprj'
tree.write(project,encoding='utf-8',xml_declaration=True)
(OUT/'build.tcl').write_text('open_project {'+project.as_posix()+'}\nset_option -top_module soundcore_headphone_top\nrun all\n',encoding='utf-8')
print(project)
