"""Release evidence and a portable full FPGA project; never opens a programmer."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess,zipfile,xml.etree.ElementTree as ET,os
from dataclasses import dataclass
R=Path(__file__).resolve().parents[1];B=R/'build/handpan_trial_20261102';O=R/'output/handpan_trial_20261102'

@dataclass(frozen=True)
class ReleaseConfig:
 slug:str='handpan_trial_20261102'
 version_code:int=20
 version_name:str='0.20-handpan-trial-offline'
 user_code:int=0x4850
 apk_name:str='声芯乐动_0.20_手碟试听版.apk'
 firmware_name:str='声芯乐动_手碟试验_完整音响版_4850.fs'
 label:str='手碟试验'
 tone_names:tuple=('二胡','口琴','空灵手碟','律动手碟')
 extra_hdl:tuple=()
 extra_tests:tuple=()
 extra_sources:tuple=()
 extra_snapshots:tuple=()
 minimum_tests:int=297
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p,q):
 q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():q.chmod(q.stat().st_mode|0o200)
 shutil.copy2(p,q)

def main(config=ReleaseConfig()):
 B=R/'build'/config.slug;O=R/'output'/config.slug
 log=(B/'build.log').read_text(encoding='utf8',errors='replace')
 assert 'Placement and routing completed'in log and 'ERROR ('not in log
 assert not re.search(r'handpan_modal32.*swept|handpan_instrument.sound.*swept',log),'Handpan audio was optimized away'
 assert "'handpan_enabled' is already implicitly declared"not in log
 assert 'handpan_modal32'in log and 'HANDPAN_AVAILABLE=1'in log
 for name in config.extra_hdl:
  module=Path(name).stem
  assert module in log and not re.search(re.escape(module)+r'.*swept',log),('Extra audio block optimized away',module)
 regeneration=B/'regenerate.log'
 if regeneration.exists():
  regenerated=regeneration.read_text(encoding='utf8',errors='replace')
  assert 'Bitstream generation completed'in regenerated and 'ERROR ('not in regenerated
 frozen=json.loads((B/'frozen_inputs.json').read_text())
 assert all(sha(B/'src'/name)==digest for name,digest in frozen.items())
 for name in ['rtl/poly_synth32_tm.v','rtl/playable_synth32.v','rtl/synth_voice.v','rtl/instrument_texture.v',
   'rtl/expressive_texture.v','rtl/expression_normalized.mem','rtl/expression_raw.mem','rtl/fsr_strike_detector.v',
   'rtl/pitch_layout.v','board/soundcore_speaker_omr_60k.cst']:
  assert (R/name).read_bytes()==(B/'before'/name).read_bytes(),name
 meta=json.loads((B/'build_metadata.json').read_text(encoding='utf8'))
 for name in ['board/pressure_i2s_additive32_core.v','board/pressure_i2s_panel_oled_ble_experiment_top.v',
   'rtl/handpan_modal32.v','rtl/front_panel_product.v','rtl/ble_control_endpoint.v','rtl/oled_status_ssd1315.v',*config.extra_hdl]:
  actual=(B/'src'/name).read_text(encoding='utf8')
  expected=(R/name).read_text(encoding='utf8').replace('"rtl/instrument_attack.vh"','"src/rtl/instrument_attack.vh"')
  for original,data in meta['assets'].items():expected=expected.replace(original,data['path'])
  expected=expected.replace((R/'rtl/handpan_sine.mem').as_posix(),(B/'src/rtl/handpan_sine.mem').as_posix())
  expected=expected.replace((R/'rtl/rock_softclip.mem').as_posix(),(B/'src/rtl/rock_softclip.mem').as_posix())
  assert actual==expected,('Compiled source does not match current source',name)
 # These test files exercise the actual core and enum; logs must exist from fresh checks.
 for name in ['modal','control','core',*config.extra_tests]:
  text=(B/f'tests/{name}.log').read_text(encoding='utf8')
  assert 'PASS'in text and 'FATAL'not in text,name
 legacy=json.loads((R/'build/low_latency_20261101/tests/results.json').read_text());assert len(legacy)==23 and all(x['passed']for x in legacy)
 pcm_file=B/'tests/pcm_results.json'
 assert pcm_file.stat().st_mtime>=(R/'rtl/handpan_modal32.v').stat().st_mtime,'PCM verification predates final RTL'
 pcm=json.loads(pcm_file.read_text(encoding='utf8'));assert len(pcm)==2
 suites=[ET.parse(p).getroot()for p in (R/'app/android/app/build/test-results/testDebugUnitTest').glob('TEST*.xml')]
 counts={k:sum(int(s.get(k,0))for s in suites)for k in ['tests','failures','errors','skipped']}
 assert counts['tests']>=config.minimum_tests and counts['failures']==counts['errors']==0
 assert 'BUILD SUCCESSFUL'in (B/'android.log').read_text(encoding='utf8')
 lint=ET.parse(R/'app/android/app/build/reports/lint-results-debug.xml').getroot()
 assert not any(x.get('severity')in ['Error','Fatal']for x in lint.findall('issue'))
 fs=B/'impl/pnr/soundcore_speaker_omr_60k.fs';assert fs.stat().st_mtime>(B/'frozen_inputs.json').stat().st_mtime
 report=(B/'impl/pnr/soundcore_speaker_omr_60k.rpt.txt').read_text(encoding='utf8')
 resources={n:re.search(r'^  '+n+r'\s+\|\s*([^|\n]+)',report,re.M)[1].strip()for n in ['Logic','Register','CLS','BSRAM','DSP']}
 timing=(B/'impl/pnr/soundcore_speaker_omr_60k_tr_content.html').read_text(encoding='utf8')
 fmax=float(re.search(r'<td>12\.288\(MHz\)</td>\s*<td>([\d.]+)\(MHz\)</td>',timing)[1]);assert fmax>=12.288
 tns=re.findall(r'<td>(Setup|Hold)</td>\s*<td>([-\d.]+)</td>\s*<td>(\d+)</td>',timing.split('Total Negative Slack Summary:')[1].split('</table>')[0])
 assert len(tns)==4 and all(float(value)==0 and int(count)==0 for _,value,count in tns),'Timing violations remain'
 code=re.search(r'UserCode:\s*(0x[\da-fA-F]+)',fs.read_text(encoding='ascii'))[1]
 assert int(code,16)==config.user_code
 sdk=Path('D:/FPGA/_Tools/android/sdk/build-tools/35.0.0');os.environ['JAVA_HOME']='D:/FPGA/_Tools/android/jdk/jdk-17.0.20.1+1'
 apk=R/'app/android/app/build/outputs/apk/debug/app-debug.apk'
 manifest=subprocess.run([str(sdk/'aapt2.exe'),'dump','badging',str(apk)],capture_output=True,text=True,encoding='utf8',check=True).stdout
 assert f"versionCode='{config.version_code}'"in manifest and 'android.permission.INTERNET'not in manifest
 signed=subprocess.run([str(sdk/'apksigner.bat'),'verify','--print-certs',str(apk)],capture_output=True,text=True,check=True)
 cert=re.search(r'certificate SHA-256 digest: (\w+)',signed.stdout)[1]
 previous=json.loads((R/'output/low_latency_20261101/release.json').read_text(encoding='utf8'))
 assert cert==previous['apk_certificate_sha256'],'APK signing identity changed'
 old=R/'output/independent_note_support_20261101/声芯乐动_0.19_自主训练音符核对_离线版.apk'
 with zipfile.ZipFile(apk)as a,zipfile.ZipFile(old)as oldzip:
  assert all(a.read(n)==oldzip.read(n)for n in oldzip.namelist()if n.startswith('assets/')),'Recognition assets changed'
 O.mkdir(parents=True,exist_ok=True)
 target=O/config.apk_name;copy(apk,target)
 firmware=O/config.firmware_name;copy(fs,firmware)
 project=ET.parse(B/'soundcore_speaker_omr_60k.gprj')
 for n in project.findall('./FileList/File'):n.set('path',Path(n.get('path')).relative_to(B).as_posix())
 archive=O/(config.label+'_完整FPGA工程.zip')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
  for p in (B/'src').rglob('*'):
   if not p.is_file():continue
   data=p.read_bytes()
   if p.suffix in ['.v','.vh']:data=data.decode('utf8').replace((B/'src').as_posix(),'src').encode('utf8')
   z.writestr(p.relative_to(B).as_posix(),data)
  z.writestr('soundcore_speaker_omr_60k.gprj',ET.tostring(project.getroot(),encoding='utf8',xml_declaration=True))
  z.writestr('build.tcl','set task_root [file dirname [file normalize [info script]]]\ncd $task_root\nopen_project [file join $task_root soundcore_speaker_omr_60k.gprj]\nset_option -top_module soundcore_speaker_omr_top\n'+f'set_option -user_code {config.user_code:08X}\nrun all\n')
 snapshots=R/'app/android/app/build/reports/paparazzi/debug'
 for method,label in [('performance','手碟演奏页面.png'),('sound','手碟音色页面.png'),*config.extra_snapshots]:
  runs=[p for p in (snapshots/'runs').glob('*.js')if f'HandpanSnapshotsTest#{method}'in p.read_text(encoding='utf8')]
  data=json.loads(re.search(r'=\s*(\[.*\]);',max(runs,key=lambda p:p.stat().st_mtime).read_text(encoding='utf8'),re.S)[1])[0]
  copy(snapshots/data['file'],O/label)
 evidence=O/'evidence';evidence.mkdir(exist_ok=True)
 optional=[B/name for name in ['resource_optimization.json','pcm_optimization_comparison.json','apk_checks.json']if (B/name).exists()]
 for p in [B/'build.log',*([regeneration]if regeneration.exists()else[]),B/'android.log',B/'frozen_inputs.json',B/'baseline.json',B/'tests/pcm_results.json',*optional,
   *[B/'tests'/name for name in ['modal.log','control.log','core.log','render0.log','render1.log',*(s+'.log'for s in config.extra_tests)]],
   *list((B/'impl/pnr').glob('*.rpt.txt')),*list((B/'impl/pnr').glob('*_tr_content.html'))]:copy(p,evidence/p.name)
 copy(R/'build/low_latency_20261101/tests/results.json',evidence/'legacy_rtl_results.json')
 if (B/'legacy_validation.json').exists():copy(B/'legacy_validation.json',evidence/'legacy_validation.json')
 release=dict(version=config.version_name,user_code=code,resources=resources,fmax_mhz=fmax,clock_mhz=12.288,timing_violations=0,
  android=counts,legacy_rtl_checks=23,new_rtl_suites=3+len(config.extra_tests),modal_pcm=pcm,pins_unchanged=True,
  single_port_optimization=json.loads((B/'resource_optimization.json').read_text(encoding='utf8'))if (B/'resource_optimization.json').exists()else None,
  recognition_assets_unchanged=True,original_instrument_arithmetic_unchanged=True,internet_permission=False,
  sram_written=False,flash_written=False,physical_sound_tested=False,physical_latency_measured=False,
  enum={str(i):name for i,name in enumerate(config.tone_names)},manual_intervals=[0,2,4,7,9,12,14],
  note='Existing native/uploaded songs keep their original instrument; handpan is free play in this trial.',
  files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size)for p in [target,firmware,archive]})
 (O/'验证结果.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
 changes=json.loads((B/'changed_sources.json').read_text(encoding='utf8'))
 changes += ['rtl/handpan_modal32.v','rtl/handpan_sine.mem','scripts/check_handpan_trial_20261102.py','scripts/check_low_latency_20261101.py',
  'scripts/prepare_handpan_trial_20261102.py','scripts/package_handpan_trial_20261102.py','tb/tb_handpan_modal32.v','tb/tb_handpan_control.v','tb/tb_handpan_core.v',
  'docs/plans/2026-11-02-handpan-trial.md','app/android/app/src/main/java/cn/soundcore/instrument/InstrumentTone.kt',
  'app/android/app/src/main/res/drawable/timbre_handpan.xml','app/android/app/src/test/java/cn/soundcore/instrument/HandpanTest.kt',
  'app/android/app/src/test/java/cn/soundcore/instrument/HandpanSnapshotsTest.kt','app/android/app/build.gradle.kts']
 with zipfile.ZipFile(O/(config.label+'_变更源码与测试.zip'),'w',zipfile.ZIP_DEFLATED)as z:
  for name in sorted(set(changes+list(config.extra_sources))):z.write(R/name,name)
  for p in (B/'diffs').glob('*.diff'):z.write(p,'diffs/'+p.name)
 print(json.dumps(release,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
