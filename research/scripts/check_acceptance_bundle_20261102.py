"""Audit the delivered files independently of the packager; no hardware access."""
from pathlib import Path
import hashlib,json,re,zipfile,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1];O=R/'output/acceptance_20261102'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
    m=json.loads((O/'manifest.json').read_text('utf8'))
    assert m['programming_performed']is False
    assert m['timing']['Setup']==m['timing']['Hold']==0
    assert m['timing']['fmax_mhz']>m['timing']['constraint_mhz']
    source=O/'source'
    hashes=json.loads((source/'source_hashes.json').read_text('utf8'))
    assert 'source_hashes.json'not in hashes
    assert all(sha(source/p)==h for p,h in hashes.items())
    with zipfile.ZipFile(O/'配套源码.zip')as z:
        assert z.testzip()is None
        assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in hashes.items())
    fpga=source/'fpga'
    project=ET.parse(fpga/'soundcore_speaker_omr_60k.gprj')
    files=[x.get('path')for x in project.findall('./FileList/File')]
    assert all(not Path(p).is_absolute()and(fpga/p).is_file()for p in files)
    references=[]
    for p in(fpga/'src').rglob('*'):
        if p.suffix in('.v','.vh'):
            for ref in re.findall(r'"(src/[^"\n]+)"',p.read_text('utf8')):
                assert(fpga/ref).is_file(),(p,ref)
                references.append(ref)
    for name in['验收导航.html','实验室验收手册.html']:
        soup=BeautifulSoup((O/name).read_text('utf8'),'html.parser')
        for el in soup.select('[src],a[href]'):
            target=el.get('src',el.get('href'))
            if target and not re.match(r'\w+://|#',target):assert(O/target).exists(),(name,target)
    for line in(O/'SHA256SUMS.txt').read_text('utf8').splitlines():
        h,name=line.split('  ',1);assert sha(O/name)==h,name
    assert m['recognition_asset_count_unchanged']==24
    assert m['android_junit']['failures']==m['android_junit']['errors']==0
    result=dict(passed=True,fpga_project_sources=len(files),relative_asset_references=len(references),
                source_files=len(hashes),source_zip_matches=True,all_delivery_hashes_match=True,
                local_links_valid=True,programming_performed=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':check()
