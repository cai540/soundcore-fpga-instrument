"""Check timing, actual PnR pin maps and regression evidence before releasing headphone images."""
from pathlib import Path
import hashlib,html,json,re,shutil,xml.etree.ElementTree as ET
from check_organic_build import timing

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/headphone_20261027'
PNR=ROOT/'board/impl/pnr'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tests=json.loads((OUT/'headphone_tests.json').read_text())
regression=json.loads((OUT/'regression.json').read_text())
assert len(tests)==4 and all(t['passed'] for t in tests)
assert len(regression)==10 and all(t['passed'] for t in regression)
protected=json.loads((OUT/'protected.json').read_text())
for name,expected in protected.items():
    assert sha(ROOT/name)==expected,'Protected file changed: '+name
speaker=json.loads((ROOT/'build/quiet_texture_20261027/build_validation.json').read_text())
assert sha(Path(speaker['firmware']))==speaker['sha256'],'Saved MAX image was overwritten'

expected_hp={'HP_BCK':'Y17','HP_WS':'AB17','HP_DIN':'AA16','PA_EN':'AB16'}
release=[]
for stem,log_name in [('headphone_check','gowin_check.log'),('soundcore_headphone','gowin_product.log')]:
    base=stem+'_60k'
    assert 'Bitstream generation completed' in (OUT/log_name).read_text()
    data=timing((PNR/(base+'_tr_content.html')).read_text())
    assert not any(data['violations'].values()) and min(data['setup_slack_ns'],data['hold_slack_ns'])>=0
    report=(PNR/(base+'.rpt.txt')).read_text();resources={}
    for key in ['Logic','BSRAM','DSP']:
        m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',report,re.M)
        if m is None:
            # Gowin omits unused resource classes. This arithmetic-only
            # check image has no BSRAM instances; the full product must
            # still have an explicit BSRAM row in its report.
            assert stem=='headphone_check' and key=='BSRAM'
            used,total=0.,118
        else:
            used,total=float(m[1]),int(m[2])
        assert used<=total
        resources[key]=dict(used=used,total=total)
    pin_html=(PNR/(base+'.pin.html')).read_text()
    anchor=pin_html.index('<h2><a name="Pinout_by_Port_Name"')
    pin_table=pin_html[anchor:pin_html.index('</table>',anchor)]
    ports={}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>',pin_table,re.S):
        cells=[html.unescape(re.sub('<[^>]+>','',x)).strip()
               for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
        if len(cells)>=5 and cells[0]!='Port Name':ports[cells[0]]=cells[2].split('/')[0]
    assert all(ports.get(name)==ball for name,ball in expected_hp.items()),ports
    assert not any(name.startswith('dac_') for name in ports)
    if stem=='headphone_check':
        assert set(ports)=={'sys_clk','rst_n','key0','key1',*expected_hp}
    else:
        cst=(ROOT/'board/pressure_i2s_panel_oled_ble_experiment_60k.cst').read_text()
        original=dict(re.findall(r'IO_LOC "([^"]+)" (\w+);',cst))
        for name,ball in original.items():
            if not name.startswith('dac_'):assert ports.get(name)==ball,(name,ports.get(name),ball)
    firmware=ROOT/('build/'+stem+'_20261027.fs')
    source_fs=PNR/(base+'.fs')
    if firmware.exists():
        assert sha(firmware)==sha(source_fs),'Refuse to overwrite a different published firmware'
    else:
        shutil.copy2(source_fs,firmware)
    user_code=re.search(r'//UserCode:\s*(\S+)',firmware.read_text())[1]
    input_hashes={}
    project=ROOT/'board'/(base+'.gprj')
    for e in ET.parse(project).findall('.//File'):
        path=(ROOT/'board'/e.attrib['path']).resolve()
        assert path.stat().st_mtime<=firmware.stat().st_mtime,'source newer than build'
        input_hashes[str(path.relative_to(ROOT))]=sha(path)
    input_hashes[str(project.relative_to(ROOT))]=sha(project)
    for suffix in ['_tr_content.html','.rpt.txt','.pin.html']:
        source_report=PNR/(base+suffix);archive=OUT/(base+suffix)
        if archive.exists():
            assert sha(archive)==sha(source_report),'Refuse to replace a different archived report'
        else:
            shutil.copy2(source_report,archive)
    data.update(firmware=str(firmware),sha256=sha(firmware),user_code=user_code,
                resources=resources,pins=ports,inputs_sha256=input_hashes)
    release.append(data)

result=dict(firmware=release,headphone_tests=tests,existing_audio_tests=regression,
            protected_files_unchanged=len(protected),sram_written=False,flash_written=False,
            previous_max_firmware_preserved=dict(path=speaker['firmware'],sha256=speaker['sha256']),
            hardware_scan_performed=False,physical_listening_verified=False,
            hardware_reason='User: peripherals not disconnected; prepare software only',
            headphone_shift_bits=2,nominal_frame_rate_hz=48000,frame_clocks=256)
programming_path=OUT/'programming_sram.json'
if programming_path.exists():
    programming=json.loads(programming_path.read_text(encoding='utf-8'))
    if (programming.get('sha256')==release[1]['sha256'] and
        programming.get('sram_program_finished') and programming.get('readback_matched')):
        assert not programming['flash_written']
        result.update(sram_written=True,hardware_scan_performed=True,
            hardware_reason='User confirmed isolation and normal remaining supplies; SRAM programmed and codes read',
            programming_record=str(programming_path),programming_record_sha256=sha(programming_path))
(OUT/'release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([dict(firmware=x['firmware'],user_code=x['user_code'],setup=x['setup_slack_ns'],
                       hold=x['hold_slack_ns'],resources=x['resources']) for x in release],indent=2))
