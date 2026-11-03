"""Package the reviewed code-only release. This script never programs hardware."""
import csv, hashlib, json, re, shutil, stat, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'
NAME='soundcore_realtime_karaoke_20261026'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def artifact(source,suffix):
    destination=BUILD/(NAME+suffix)
    assert destination.parent.resolve()==BUILD.resolve()
    if destination.exists():
        # Gowin marks generated bitstreams read-only; copy2 preserves that.
        destination.chmod(destination.stat().st_mode|stat.S_IWRITE)
    shutil.copy2(ROOT/source,destination)
    return dict(path=str(destination),bytes=destination.stat().st_size,sha256=sha(destination))

fpga_log=(BUILD/'realtime_karaoke_gowin.log').read_text(errors='replace')
android_log=(BUILD/'realtime_karaoke_android.log').read_text(errors='replace')
assert 'Bitstream generation completed' in fpga_log
assert 'BUILD SUCCESSFUL' in android_log
timing=BeautifulSoup((ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k_tr_content.html').read_text(),'html.parser')
violations={}
for title in ('Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints'):
    cell=timing.find('td',string=title)
    violations[title]=int(cell.find_next_sibling('td').get_text(strip=True))
assert not any(violations.values())
resource_text=(ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.rpt.txt').read_text(errors='replace')
resources={}
for label,key in [('Logic','logic'),('BSRAM','bsram'),('DSP','dsp')]:
    match=re.search(r'^\s*'+label+r'\s*\|\s*([\d.]+)/([\d.]+)',resource_text,re.M)
    assert match,label
    resources[key+'_used']=float(match[1]);resources[key+'_total']=int(match[2])
def slack(anchor):
    table=timing.find('a',attrs={'name':anchor}).parent.find_next('table')
    return float(table.find_all('tr')[1].find_all('td')[1].get_text(strip=True))
tests=[]
for p in sorted((ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')):
    t=ET.parse(p).getroot()
    result={key:int(t.attrib.get(key,0)) for key in ('tests','failures','errors','skipped')}
    assert result['failures']==0 and result['errors']==0
    tests.append(dict(name=t.attrib['name'],**result))
assert tests
logs=['tb_realtime_notes','tb_remote_note_bridge','tb_realtime_voice_integration','tb_ble_realtime_endpoint','tb_ble_control_endpoint',
      'tb_oled_karaoke_integration','tb_oled_force_geometry','tb_oled_event_refresh','tb_oled_product_text',
      'tb_oled_ble_stable','tb_oled_reconnect','tb_oled_dual_address','tb_audio_song_full_playback',
      'tb_lyric_position','physical_latency']
evidence={}
for name in logs:
    p=BUILD/(name+'.log');body=p.read_text(errors='replace')
    assert 'PASS:' in body and 'FATAL:' not in body,name
    evidence[name]=dict(path=str(p),sha256=sha(p))
with (BUILD/'physical_latency.csv').open() as f:latencies=list(csv.DictReader(f))
ms=[float(r['voltage_step_to_i2s_word_ns'])/1e6 for r in latencies]
report=json.loads((ROOT/'songs/karaoke_review/report.json').read_text(encoding='utf-8'))
source=[]
for base,pattern in [('rtl','*.v'),('board','*.v'),('board','*.cst'),('board','*.gprj'),
                     ('app/android/app/src','*.kt'),('songs/rom_karaoke','*.mem'),
                     ('songs','*.py'),('tb','*.v'),('tb','*.py'),('scripts','*.py')]:
    source.extend((ROOT/base).rglob(pattern))
snapshot=BUILD/(NAME+'_sources.json')
snapshot.write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in sorted(set(source))},indent=2)+'\n',encoding='utf-8')
manifest=dict(
    release=NAME,created=datetime.now().isoformat(timespec='seconds'),
    hardware_programmed=False,flash_written=False,
    artifacts=dict(fpga=artifact('board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.fs','.fs'),
                   apk=artifact('app/android/app/build/outputs/apk/debug/app-debug.apk','.apk')),
    resources=resources,
    timing=dict(violations=violations,setup_slack_ns=slack('Setup_Slack_Table'),hold_slack_ns=slack('Hold_Slack_Table')),
    android_suites=tests,rtl_evidence=evidence,song_reports=report,
    physical_latency_simulation=dict(cases=len(ms),min_ms=min(ms),max_ms=max(ms),
        scope='ADC voltage step after worst scan phase to decoded I2S word abs>=64; not mechanical-to-analog measurement'),
    realtime_notes=dict(opcode='0x24',payload='held mask, attack mask, velocity',app_min_interval_ms=16,
        firmware_pending_limit_ms=40,individually_acknowledged=False,late_released_attacks_discarded=True),
    source_snapshot=dict(path=str(snapshot),sha256=sha(snapshot)),
    pending=['matching firmware/APK hardware BLE multi-touch test','both songs listening review',
             'real OLED lyric sweep/pause/restore','mechanical input to analog audio latency measurement'])
(BUILD/'realtime_karaoke_release_20261026.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(artifacts=manifest['artifacts'],android_tests=sum(t['tests'] for t in tests),
    timing=manifest['timing'],hardware_programmed=False),ensure_ascii=False,indent=2))
