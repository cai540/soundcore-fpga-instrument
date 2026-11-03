"""Read-only source/resource audit; no claim of an implemented optimization."""
from pathlib import Path
import json,csv,hashlib,re
from lxml import html

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/engineering_upgrade_20261028/resource_audit';OUT.mkdir(parents=True,exist_ok=True)
release=json.loads((ROOT/'build/headphone_20261027/release.json').read_text(encoding='utf-8'))
baseline=next(x for x in release['firmware'] if 'soundcore_headphone_' in x['firmware'])
p=ROOT/'board/impl/gwsynthesis/soundcore_headphone_60k_syn_resource.html'
tree=html.fromstring(p.read_bytes());cells=[' '.join(x.text_content().split()).replace('\xa0',' ') for x in tree.xpath('//td')]
assert len(cells)%8==0
cols=['module','register','alu','lut','dsp_operations','bsram','ssram','rom16']
rows=[dict(zip(cols,cells[i:i+8])) for i in range(0,len(cells),8)]
with (OUT/'hierarchy_resources.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,cols);w.writeheader();w.writerows(rows)
inputs={}
for rel,expected in baseline['inputs_sha256'].items():
    f=ROOT/rel;actual=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
    inputs[rel]={'expected':expected,'actual':actual,'match':expected==actual}
firmware=ROOT/'build/soundcore_headphone_20261027.fs'
checks={
 'baseline':{'user_code':baseline['user_code'],'resources':baseline['resources'],
 'setup_slack_ns':baseline['setup_slack_ns'],'hold_slack_ns':baseline['hold_slack_ns'],
 'firmware_sha256':hashlib.sha256(firmware.read_bytes()).hexdigest(),
 'firmware_matches_release':hashlib.sha256(firmware.read_bytes()).hexdigest()==baseline['sha256']},
 'percentages':{k:round(100*v['used']/v['total'],3) for k,v in baseline['resources'].items()},
 'source_input_hashes':inputs,
 'hierarchy_rows':len(rows),
 'primary_clock_network_utilization':'8/8 in PnR; includes automatically promoted high-fanout nets; not proof of eight independent clock domains',
 'candidate_hotspots':[
 {'file':'rtl/playable_synth32.v','finding':'32 replicated 32x17-bit pitch multiplications and 32 note tables',
  'proposal':'snapshot frame inputs, share lookup and pipelined pitch arithmetic',
  'status':'design only; no optimized resource count or equivalence result'},
 {'file':'board/pressure_i2s_additive32_core.v','finding':'offline player has a separate synth_voice/texture path',
  'proposal':'evaluate unified engine with explicit concurrency policy; 31 live plus 1 song if reserving a voice',
  'status':'second priority; cannot remove functionality silently'},
 {'file':'rtl/fsr_strike_detector.v','finding':'four-sample peak window; rise_code deliberately not used in velocity mapping',
  'proposal':'evaluate bounded early peak prediction with confidence and chord-preserving rejection',
  'status':'requires real strike recordings before a useful technical contribution can be established'}],
 'physical_dsp_units_are_not_synthesis_operation_counts':True,
 'no_rtl_or_apk_modified':True,
 'inputs_hash_note':'Current files are checked against the saved release; any mismatch must be reviewed, not silently treated as baseline.'}
(OUT/'audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'resources':checks['percentages'],
 'input_hash_mismatches':[k for k,v in inputs.items() if not v['match']],
 'firmware_matches_release':checks['baseline']['firmware_matches_release']},ensure_ascii=False,indent=2))
