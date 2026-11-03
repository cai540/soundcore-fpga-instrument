"""Fail-closed release of the saved-profile early-pressure experiment."""
from pathlib import Path
import hashlib,html,json,re,shutil
from check_organic_build import timing
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/early_pressure_20261028'
PNR=OUT/'gowin/impl/pnr';NAME='soundcore_early_pressure_60k'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((OUT/'baseline/release.json').read_text())
assert sha(Path(baseline['firmware']))==baseline['sha256'],'Shared-pitch baseline image changed'
frozen=json.loads((OUT/'baseline/source_sha256.json').read_text())
changed=[name.replace('\\','/') for name,h in frozen.items() if sha(ROOT/name)!=h]
assert set(changed)=={'rtl/fsr_strike_detector.v','board/pressure_i2s_additive32_core.v',
    'board/pressure_i2s_panel_oled_ble_experiment_top.v'},changed
protected=json.loads((OUT/'baseline/protected.json').read_text())
for name,h in protected.items():assert sha(ROOT/name)==h,'Protected file changed: '+name
inputs=json.loads((OUT/'build_input_sha256.json').read_text())
for name,h in inputs.items():assert sha(ROOT/name)==h,'Input changed during build: '+name
tests=json.loads((OUT/'tests.json').read_text())
required={'tb_pressure_saved_profile','tb_early_pressure_detector','tb_fsr_trace_capture',
    'tb_fsr_strike_detector','tb_pressure_trace_replay','tb_early_pressure_allocator',
    'tb_panel_audio_integration','tb_panel_audio_integration_default',
    'tb_realtime_voice_integration','tb_pressure_voice_release'}
assert {x['test'] for x in tests}==required and all(x['passed'] for x in tests)
replay=json.loads((OUT/'replay/checks.json').read_text());assert replay['passed']
assert 'Bitstream generation completed' in (OUT/'gowin_build.log').read_text(encoding='utf-8-sig')
data=timing((PNR/(NAME+'_tr_content.html')).read_text())
assert not any(data['violations'].values()) and min(data['setup_slack_ns'],data['hold_slack_ns'])>=0
resources={};rpt=(PNR/(NAME+'.rpt.txt')).read_text()
for key in ['Logic','Register','BSRAM','DSP']:
    m=re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)',rpt,re.M);assert m,key
    used,total=float(m[1]),int(m[2]);assert used<=total
    resources[key]={'used':used,'total':total,'utilization_percent':100*used/total,
        'delta_from_shared_pitch':used-baseline['resources'][key]['used']}
ph=(PNR/(NAME+'.pin.html')).read_text();anchor=ph.index('<h2><a name="Pinout_by_Port_Name"')
table=ph[anchor:ph.index('</table>',anchor)];ports={}
for row in re.findall(r'<tr[^>]*>(.*?)</tr>',table,re.S):
    cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
    if len(cells)>=5 and cells[0]!='Port Name':ports[cells[0]]=cells[2].split('/')[0]
old_release=json.loads((ROOT/'build/headphone_20261027/release.json').read_text())
old=next(x for x in old_release['firmware'] if 'soundcore_headphone_' in x['firmware'])
assert ports==old['pins'],'Public pin mapping changed'
image=PNR/(NAME+'.fs');target=ROOT/'build/soundcore_headphone_early_pressure_20261028.fs'
for name in inputs:assert (ROOT/name).stat().st_mtime<=image.stat().st_mtime,'Source newer than image: '+name
if target.exists():assert sha(target)==sha(image),'Refuse to overwrite different published experiment'
else:shutil.copy2(image,target)
for source,dest in [(NAME+'.rpt.txt','resource_report.txt'),(NAME+'_tr_content.html','timing_report.html'),
                    (NAME+'.pin.html','pin_report.html')]:shutil.copy2(PNR/source,OUT/dest)
code=re.search(r'//UserCode:\s*(\S+)',target.read_text())[1]
profile=json.loads((OUT/'profile_manifest.json').read_text())
assert profile['profile_sha256']==sha(ROOT/'config/pressure_profile_v1.json')
result={**data,'firmware':str(target),'sha256':sha(target),'user_code':code,'resources':resources,
    'baseline':{k:baseline[k] for k in ['firmware','sha256','user_code','resources','setup_slack_ns','hold_slack_ns']},
    'saved_profile':profile,'manual_calibration_each_boot':False,'automatic_zero_samples_per_pad':16,
    'experiment_enabled':True,'legacy_fallback_enabled':True,
    'baseline_peak_follow_samples':4,'earliest_candidate_follow_samples':2,
    'independent_voices':32,'nominal_sample_rate_hz':48000,'audio_frame_clocks':256,
    'audio_pitch_pipeline_preserved':True,'audio_pitch_completion_clocks':193,
    'tests':tests,'replay_checks':replay,'protected_files_unchanged':len(protected),
    'pins':ports,'pins_unchanged':True,'changed_existing_product_sources':changed,
    'source_sha256':inputs,'recorder':{'unit_tested':True,'included_in_product_bitstream':False,
        'ble_export_implemented':False},
    'sram_written':False,'flash_written':False,'hardware_scan_performed':False,
    'real_trace_training_performed':False,'end_to_end_latency_measured':False,
    'listening_verified':False,'static_curve_bit_exact_checked_inputs':4096,
    'evidence_sha256':{p.name:sha(p) for p in [OUT/'tests.json',OUT/'replay/checks.json',
        OUT/'resource_report.txt',OUT/'timing_report.html',OUT/'gowin_build.log']}}
(OUT/'release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['firmware','user_code','resources','setup_slack_ns','hold_slack_ns','protected_files_unchanged']},ensure_ascii=False,indent=2))
