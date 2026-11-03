from pathlib import Path
import xml.etree.ElementTree as E
r=Path(__file__).resolve().parent
for p in (r/'src').rglob('*'):
 if p.is_file() and p.suffix in {'.v','.vh','.tcl','.sdc'}:
  t=p.read_text(encoding='utf-8');s=t.replace('@FPGA_ROOT@',r.as_posix())
  if s!=t:p.write_text(s,encoding='utf-8')
p=r/'soundcore.gprj';tree=E.parse(p)
for f in tree.findall('.//File'):
 v=f.get('path');q=Path(v)
 if not q.is_absolute():q=r/q
 assert q.is_file(),q
 f.set('path',q.as_posix())
tree.write(p,encoding='utf-8',xml_declaration=True)
print('Configured',r)
