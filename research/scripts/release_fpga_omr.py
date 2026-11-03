"""Collect tested source/model/bitstream evidence; never call a programmer."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
from lxml import html
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/fpga_omr_20261031';OUT=ROOT/'output/fpga_omr_20261031'
OUT.mkdir(parents=True,exist_ok=True)

def report(folder,name):
    p=BUILD/folder/'impl/pnr';txt=(p/(name+'.rpt.txt')).read_text(encoding='utf8')
    resources={}
    for key in ['Logic','Register','BSRAM','DSP']:
        match=re.search(r'^\s*'+key+r'\s+\|\s+([\d.]+)/([\d.]+)',txt,re.M)
        assert match,key
        resources[key]={'used':float(match[1]),'total':float(match[2])}
    tree=html.fromstring((p/(name+'_tr_content.html')).read_bytes());violations={}
    for row in tree.xpath('//tr'):
        cells=[' '.join(c.text_content().split())for c in row.xpath('./td')]
        if len(cells)==2 and'Violated'in cells[0]:violations[cells[0]]=int(cells[1])
    assert violations and not any(violations.values()),violations
    slacks={}
    for kind in ['Setup','Hold']:
        tables=tree.xpath(f'//a[@name="{kind}_Slack_Table"]/../following-sibling::table[1]');assert tables
        values=[float(row.xpath('./td')[1].text_content())for row in tables[0].xpath('.//tr')if len(row.xpath('./td'))>1]
        slacks[kind]=min(values)
    return {'resources':resources,'violations':violations,'slack_ns':slacks,'firmware':p/(name+'.fs')}

model=json.loads((BUILD/'model/manifest.json').read_text(encoding='utf8'))
verified=json.loads((BUILD/'verification.json').read_text(encoding='utf8'))
assert verified['model_bit_exact'] and verified['protocol_rtl_passed']
assert 'PASS realtime note during inference' in (BUILD/'simulation/integrated.log').read_text()
standalone=report('gowin_standalone','omr_uart_60k');integrated=report('gowin_integrated','soundcore_omr_60k')
firmware=OUT/'soundcore_含FPGA识谱核_待上板.fs';shutil.copyfile(integrated['firmware'],firmware)
for report_data in [standalone,integrated]:report_data['firmware']=str(report_data['firmware'])
snapshot=json.loads((BUILD/'baseline_sources.json').read_text())
frozen=ROOT/'output/melody_workbench_20261028/source'
original_changes=[]
for relative in snapshot['snapshot_sha256']:
    path=Path(relative)
    if (frozen/path).read_bytes()!=(ROOT/path).read_bytes():original_changes.append(relative)
assert not original_changes,'Current product differs from frozen input; do not call this current candidate'
release={'status':'trained_bit_exact_synthesized_routed_physical_acceptance_pending',
 'model':{k:model[k]for k in ['model','model_crc32','weights','biases','shift1','metrics']},
 'standalone':standalone,'integrated':integrated,'verification':verified,'integrated_ble_realtime_and_legacy_query_passed':True,
 'core_cycles':34326,'core_compute_ms_at_50mhz':34326/50000,'core_compute_ms_at_audio_clock':34326/12288.1356,
 'is_end_to_end_latency_measurement':False,'gpio_changed':False,'source_matches_current_product_before_experiment':True,
 'sram_written':False,'flash_written':False,'physical_inference_verified':False,'phone_ui_integrated':False,
 'fully_replaces_visual_api':False,'asr_api_replaced':False,'formal_website_or_apk_changed':False,
 'firmware':str(firmware),'firmware_sha256':hashlib.sha256(firmware.read_bytes()).hexdigest()}
release['build_input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in [BUILD/'src',BUILD/'baseline',BUILD/'model'] for p in folder.rglob('*')
    if p.is_file() and p.suffix in ('.v','.vh','.cst','.sdc','.hex')}
(OUT/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
for rel in ['fpga_omr/model.py','fpga_omr/protocol.py','fpga_omr/batch.py','fpga_omr/__init__.py','fpga_omr/manual_non_notes.json',
            'rtl/omr_symbol_mlp.v','rtl/omr_frame_endpoint.v','rtl/omr_serial_endpoint.v','rtl/ble_frame_parser.v','rtl/uart_8n1_9600.v',
            'scripts/train_fpga_omr.py','scripts/verify_fpga_omr.py','scripts/verify_integrated_omr.py','scripts/build_fpga_omr.py',
            'scripts/recognize_sheet_fpga.mjs','scripts/release_fpga_omr.py','tests/test_fpga_omr.py']:
    target=OUT/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
for rel in ['rtl/ble_control_endpoint.v','board/pressure_i2s_panel_oled_ble_experiment_top.v']:
    target=OUT/'source/integration'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BUILD/'baseline'/rel,target)
for name in ['manifest.json','integer_weights.npz','w1.hex','b1.hex','w2.hex','b2.hex']:
    target=OUT/'model'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(BUILD/'model'/name,target)
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
for filename in ['model.log','protocol.log','integrated.log']:
    shutil.copyfile(BUILD/'simulation'/filename,evidence/filename)
for name,result in [('standalone',standalone),('integrated',integrated)]:
    source=Path(result['firmware']).parent
    prefix=Path(result['firmware']).stem
    for suffix in ['.rpt.txt','_tr_content.html']:shutil.copyfile(source/(prefix+suffix),evidence/(name+suffix))
shutil.copyfile(ROOT/'docs/fpga_omr_20261031.md',OUT/'说明与复现.md')
digest={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file() and p.suffix!='.zip' and p.name!='SHA256.json'}
(OUT/'SHA256.json').write_text(json.dumps(digest,ensure_ascii=False,indent=2),encoding='utf8')
archive=OUT/'FPGA轻量识谱核_候选验证包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
    for p in OUT.rglob('*'):
        if p.is_file() and p!=archive:z.write(p,p.relative_to(OUT))
print(json.dumps({'standalone':standalone['resources'],'integrated':integrated['resources'],'slack_ns':integrated['slack_ns'],'output':str(OUT)},ensure_ascii=False))
