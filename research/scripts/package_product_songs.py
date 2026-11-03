"""Package the new song catalogue without invoking any programmer."""
import argparse,hashlib,json,re,shutil,stat,xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
args_parser=argparse.ArgumentParser()
args_parser.add_argument('--name',default='soundcore_zuguo_qiansixi_20261026')
args_parser.add_argument('--log-prefix',default='product_songs')
args_parser.add_argument('--android-log',help='Reuse validated Android log when App sources/APK are unchanged')
args_parser.add_argument('--evidence-prefix',default='')
args_parser.add_argument('--data-log',default='product_song_data_test.log')
args_parser.add_argument('--data-tests',type=int,default=4)
args_parser.add_argument('--manifest',default='product_songs_release_20261026.json')
args_parser.add_argument('--extra-evidence',action='append',default=[])
args=args_parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build';NAME=args.name
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert 'Bitstream generation completed' in (BUILD/(args.log_prefix+'_gowin.log')).read_text(errors='replace')
assert 'BUILD SUCCESSFUL' in (BUILD/(args.android_log or args.log_prefix+'_android.log')).read_text(errors='replace')
timing=BeautifulSoup((ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k_tr_content.html').read_text(),'html.parser')
violations={}
for title in ('Numbers of Setup Violated Endpoints','Numbers of Hold Violated Endpoints'):
    violations[title]=int(timing.find('td',string=title).find_next_sibling('td').get_text(strip=True))
assert not any(violations.values())
def slack(anchor):
    table=timing.find('a',attrs={'name':anchor}).parent.find_next('table')
    return float(table.find_all('tr')[1].find_all('td')[1].get_text(strip=True))
resource_text=(ROOT/'board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.rpt.txt').read_text(errors='replace')
resources={}
for label,key in [('Logic','logic'),('BSRAM','bsram'),('DSP','dsp')]:
    m=re.search(r'^\s*'+label+r'\s*\|\s*([\d.]+)/([\d.]+)',resource_text,re.M);assert m
    resources[key+'_used']=float(m[1]);resources[key+'_total']=int(m[2])
tests=[]
for p in (ROOT/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    t=ET.parse(p).getroot();result={k:int(t.attrib.get(k,0)) for k in ('tests','failures','errors','skipped')}
    assert result['failures']==result['errors']==0;tests.append(dict(name=t.attrib['name'],**result))
assert tests
names=['tb_audio_song_full_playback','tb_lyric_position','tb_score_midi_review_rom',
    'tb_product_song_guide','tb_oled_karaoke_render','tb_oled_karaoke_integration']+args.extra_evidence
evidence={}
for name in names:
    p=BUILD/(args.evidence_prefix+name+'.log');s=p.read_text(errors='replace');assert 'PASS:' in s and 'FATAL:' not in s,name
    evidence[name]=dict(path=str(p),sha256=sha(p))
assert 'OK' in (BUILD/args.data_log).read_text(errors='replace')
def copy(source,suffix):
    destination=BUILD/(NAME+suffix)
    if destination.exists():destination.chmod(destination.stat().st_mode|stat.S_IWRITE)
    shutil.copy2(ROOT/source,destination)
    return dict(path=str(destination),bytes=destination.stat().st_size,sha256=sha(destination))
files=[]
for base,pattern in [('rtl','*.v'),('board','*.v'),('board','*.vh'),('board','*.gprj'),('board','*.cst'),
    ('app/android/app/src','*.kt'),('songs/rom_product_songs','*'),('songs/product_song_review','*.csv'),
    ('songs/product_song_review','*.json'),('songs/zuguo_syllable_review','*.json'),
    ('songs/zuguo_octave_review','*.json'),('songs/zuguo_octave_review','*.csv'),
    ('songs/zuguo_syllable_review','*.csv'),('songs','*.py'),('tb','*.v'),('tb','*.py'),('scripts','*.py')]:
    files.extend(p for p in (ROOT/base).rglob(pattern) if p.is_file())
snapshot=BUILD/(NAME+'_sources.json')
snapshot.write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},indent=2)+'\n',encoding='utf-8')
review=json.loads((ROOT/'songs/product_song_review/review.json').read_text(encoding='utf-8'))
manifest=dict(release=NAME,created=datetime.now().isoformat(timespec='seconds'),
    hardware_programmed=False,flash_written=False,
    artifacts=dict(fpga=copy('board/impl/pnr/pressure_i2s_panel_oled_ble_experiment_60k.fs','.fs'),
        apk=copy('app/android/app/build/outputs/apk/debug/app-debug.apk','.apk')),
    catalog=review['catalog'],printed_key=review['printed_key'],playback_key=review['audio_and_playback_key'],
    vocal_trim=[review['trim_start_s'],review['trim_end_s']],
    source_audio=dict(path='songs/source/wodezuguo_vocals_20261026.mp3',sha256=sha(ROOT/'songs/source/wodezuguo_vocals_20261026.mp3')),
    source_score=dict(path='songs/source/wodezuguo_score_20261026.jpg',sha256=sha(ROOT/'songs/source/wodezuguo_score_20261026.jpg')),
    timing=dict(violations=violations,setup_slack_ns=slack('Setup_Slack_Table'),hold_slack_ns=slack('Hold_Slack_Table')),
    resources=resources,android_suites=tests,
    android_validation_log=args.android_log or args.log_prefix+'_android.log',
    android_validation_reused=bool(args.android_log),rtl_evidence=evidence,data_tests=args.data_tests,
    source_snapshot=dict(path=str(snapshot),sha256=sha(snapshot)),
    preserved=['current-finger BLE snapshots','strict correct-note-only guidance','automatic target bank',
        'normalized effects','pressure dynamics','accepted Zuguo melody and syllable timing unchanged'],
    pending=['song listening review','matching firmware/APK hardware test','actual OLED sync','analog end-to-end latency measurement'])
if 'original_reference_revision' in review:
    manifest['original_reference_revision']=review['original_reference_revision']
    manifest['source_original']=dict(path='songs/source/wodezuguo_original_20261026.mp3',sha256=sha(ROOT/'songs/source/wodezuguo_original_20261026.mp3'))
if 'chilege_revision' in review:
    manifest['chilege_revision']=review['chilege_revision']
    manifest['replacement_sources']=[dict(path='songs/source/'+name,sha256=sha(ROOT/'songs/source'/name)) for name in ('chilege_original_20261026.mp3','chilege_vocals_20261026.wav','chilege_score_20261026.jpg')]
(BUILD/args.manifest).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(artifacts=manifest['artifacts'],catalog=manifest['catalog'],resources=resources,
    timing=manifest['timing'],android_tests=sum(t['tests'] for t in tests),hardware_programmed=False),ensure_ascii=False,indent=2))
