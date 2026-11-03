"""Release the isolated resource optimization only after verified evidence."""
from pathlib import Path
import hashlib,html,json,re,shutil,xml.etree.ElementTree as ET
from check_organic_build import timing
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/shared_pitch_20261028'
PNR=OUT/'gowin/impl/pnr';NAME='soundcore_shared_pitch_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline_release=json.loads((ROOT/'build/headphone_20261027/release.json').read_text())
base=next(x for x in baseline_release['firmware'] if 'soundcore_headphone_' in x['firmware'])
assert sha(Path(base['firmware']))==base['sha256'],'Published baseline bitstream changed'
tests=json.loads((OUT/'all_tests.json').read_text())
assert len(tests)==11 and all(t['passed'] for t in tests),'Current regression set not complete'
assert any('16384 pitch cases' in t['output'] for t in tests)
assert any('1200 bit-exact PCM frames' in t['output'] for t in tests)
baseline_tests=json.loads((OUT/'baseline_all_tests.json').read_text())
assert len(baseline_tests)==2 and all(t['passed'] for t in baseline_tests)
protected=json.loads((OUT/'baseline/protected.json').read_text())
for name,expected in protected.items():assert sha(ROOT/name)==expected,'Protected file changed: '+name
source_base=json.loads((OUT/'baseline/source_sha256.json').read_text())
changed=[name for name,expected in source_base.items() if sha(ROOT/name)!=expected]
assert changed==['rtl\\playable_synth32.v'] or changed==['rtl/playable_synth32.v'],changed
log=(OUT/'gowin_build.log').read_text(encoding='utf-8')
assert 'Bitstream generation completed' in log
data=timing((PNR/(NAME+'_tr_content.html')).read_text())
assert not any(data['violations'].values()) and min(data['setup_slack_ns'],data['hold_slack_ns'])>=0
rpt=(PNR/(NAME+'.rpt.txt')).read_text();resources={}
for key in ['Logic','Register','BSRAM','DSP']:
    m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',rpt,re.M);assert m,key
    used,total=float(m[1]),int(m[2]);assert used<=total
    resources[key]={'used':used,'total':total,'utilization_percent':100*used/total}
baseline_rpt=(ROOT/'build/headphone_20261027/soundcore_headphone_60k.rpt.txt').read_text()
before={}
for key in resources:
    m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',baseline_rpt,re.M)
    before[key]={'used':float(m[1]),'total':int(m[2])}
comparison={k:{'before':before[k]['used'],'after':v['used'],
    'delta':v['used']-before[k]['used'],
    'relative_reduction_percent':100*(before[k]['used']-v['used'])/before[k]['used']} for k,v in resources.items()}
ph=(PNR/(NAME+'.pin.html')).read_text();anchor=ph.index('<h2><a name="Pinout_by_Port_Name"')
table=ph[anchor:ph.index('</table>',anchor)];ports={}
for row in re.findall(r'<tr[^>]*>(.*?)</tr>',table,re.S):
    cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
    if len(cells)>=5 and cells[0]!='Port Name':ports[cells[0]]=cells[2].split('/')[0]
assert ports==base['pins'],'Pin mapping changed'
image=PNR/(NAME+'.fs');target=ROOT/'build/soundcore_headphone_shared_pitch_20261028.fs'
if target.exists():assert sha(target)==sha(image),'Refuse to replace different published candidate'
else:shutil.copy2(image,target)
code=re.search(r'//UserCode:\s*(\S+)',target.read_text())[1]
for source,dest in [(NAME+'.rpt.txt','resource_report.txt'),(NAME+'_tr_content.html','timing_report.html'),
                    (NAME+'.pin.html','pin_report.html')]:shutil.copy2(PNR/source,OUT/dest)
project=OUT/'gowin/soundcore_shared_pitch_60k.gprj'
inputs=[project]+[Path(e.attrib['path']) for e in ET.parse(project).findall('.//File')]
for p in inputs:assert p.stat().st_mtime<=image.stat().st_mtime,'Source changed after build: '+str(p)
result={**data,'resources':resources,'comparison':comparison,
 'baseline':{'firmware':base['firmware'],'sha256':base['sha256'],'user_code':base['user_code'],
             'resources':before,'setup_slack_ns':base['setup_slack_ns'],'hold_slack_ns':base['hold_slack_ns']},
 'firmware':str(target),'sha256':sha(target),'user_code':code,
 'independent_voices':32,'nominal_sample_rate_hz':48000,'audio_frame_clocks':256,
 'shared_pitch_clocks':64,'voice_core_clocks':128,'wrapper_completion_clocks':193,
 'pitch_combinations_checked':16384,'bit_exact_pcm_frames':1200,
 'dynamic_reference_contract':'Controls are captured at sample_tick for both implementations; legacy unconstrained mid-frame reads are intentionally replaced.',
 'tests':tests,'baseline_tests_after_testbench_corrections':baseline_tests,
 'testbench_changes':'Completed-frame checks; onset audition window; wait for actual voice31 envelope rather than counting old mixed samples.',
 'protected_files_unchanged':len(protected),'pins_unchanged':True,'changed_product_sources':changed,
 'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in inputs},
 'evidence_sha256':{p.name:sha(p) for p in [OUT/'all_tests.json',OUT/'resource_report.txt',OUT/'timing_report.html',OUT/'gowin_build.log']},
 'sram_written':False,'flash_written':False,'hardware_scan_performed':False,
 'physical_listening_verified':False,'end_to_end_latency_measured':False}
(OUT/'release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['firmware','user_code','resources','comparison','setup_slack_ns','hold_slack_ns','protected_files_unchanged']},ensure_ascii=False,indent=2))
