"""Publish only the fully checked, opt-in continuous-expression candidate."""
from pathlib import Path
import hashlib, html, json, re, shutil
from check_organic_build import timing

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/expression_20261028'
PNR = OUT / 'gowin_rom/impl/pnr'
NAME = 'soundcore_expression_60k'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

baseline = json.loads((OUT/'baseline/release.json').read_text(encoding='utf-8'))
assert sha(Path(baseline['firmware'])) == baseline['sha256'], 'Previous candidate changed'
frozen = json.loads((OUT/'baseline/source_sha256.json').read_text())
for name, digest in frozen.items():
    assert sha(OUT/'baseline'/name) == digest, 'Frozen baseline changed: '+name
changed = [name.replace('\\', '/') for name, digest in frozen.items() if sha(ROOT/name) != digest]
assert set(changed) == {
    'rtl/poly_synth32_tm.v', 'rtl/playable_synth32.v', 'rtl/fsr_strike_detector.v',
    'rtl/strike_voice_allocator32.v', 'rtl/synth_voice.v',
    'board/pressure_i2s_additive32_core.v',
    'board/pressure_i2s_panel_oled_ble_experiment_top.v'}, changed
protected = json.loads((OUT/'baseline/protected.json').read_text())
for name, digest in protected.items():
    assert sha(ROOT/name) == digest, 'Protected file changed: '+name
inputs = json.loads((OUT/'build_input_sha256.json').read_text())
for name, digest in inputs.items():
    assert sha(ROOT/name) == digest, 'Build input changed: '+name

tests = json.loads((OUT/'tests.json').read_text())
required = {'tb_pressure_expression32', 'tb_expression_bitexact', 'tb_expression_synth',
            'tb_expression_isolation', 'tb_expression_rom_equiv', 'tb_expression_texture',
            'tb_expression_core', 'tb_early_pressure_allocator', 'tb_pressure_voice_release',
            'tb_realtime_voice_integration', 'tb_panel_audio_integration', 'tb_playable_synth32'}
assert len(tests) == len(required) and {t['test'] for t in tests} == required
assert all(t['passed'] for t in tests), 'Regression failure'
spectral = json.loads((OUT/'spectral_validation.json').read_text())
assert spectral['actual_rtl_anchor_cases'] == 630
assert spectral['reference_interpolation_cases'] == 17920
assert spectral['all_reference_interpolation_span_db'] < 1
assert all(x['normalized_span_db'] < 1 for x in spectral['measurements'])
audition = json.loads((OUT/'audition.json').read_text())
assert audition['actual_rtl_source'] and audition['samples_per_ablation'] == 576000
for name, digest in audition['capture_source_sha256'].items():
    assert sha(ROOT/name) == digest, 'Stale audition: '+name
for name in ['rtl/expression_normalized.mem', 'rtl/expression_raw.mem']:
    assert (ROOT/name).stat().st_mtime <= (OUT/'audition.json').stat().st_mtime
assert max(audition['peak_by_variant'].values()) < 32760
for path in audition['preview_files'].values():
    assert Path(path).stat().st_size > 1000
audio_checks = json.loads((OUT/'audio_validation.json').read_text())
assert audio_checks['passed'] and len(audio_checks['previews']) == 8
assert audio_checks['actual_mp3_decoding_checked']
for item in audio_checks['previews']:
    audio_path = Path(audition['preview_files'][item['name']])
    assert sha(audio_path) == item['mp3_sha256']
    assert sha(audio_path.with_suffix('.wav')) == item['wav_sha256']
profile = json.loads((OUT/'profile_validation.json').read_text())
assert profile['profile_sha256'] == sha(ROOT/'config/expression_profile_v1.json')
for name, digest in profile['generated_sha256'].items():
    assert sha(ROOT/name) == digest, 'Profile output changed: '+name
assert baseline['saved_profile']['profile_sha256'] == sha(ROOT/'config/pressure_profile_v1.json')
log = OUT/'gowin_rom_build.log'
assert 'Bitstream generation completed' in log.read_text(encoding='utf-8-sig')
data = timing((PNR/(NAME+'_tr_content.html')).read_text())
assert not any(data['violations'].values())
assert min(data['setup_slack_ns'], data['hold_slack_ns']) >= 0
resources = {}
rpt = (PNR/(NAME+'.rpt.txt')).read_text()
for key in ['Logic', 'Register', 'BSRAM', 'DSP']:
    m = re.search(r'^\s*'+key+r'\s*\|\s*([\d.]+)/([\d.]+)', rpt, re.M)
    assert m, key
    used, total = float(m[1]), int(m[2])
    assert used <= total
    resources[key] = dict(used=used, total=total, utilization_percent=100*used/total,
                          delta_from_early_pressure=used-baseline['resources'][key]['used'])
pin_html = (PNR/(NAME+'.pin.html')).read_text()
anchor = pin_html.index('<h2><a name="Pinout_by_Port_Name"')
table = pin_html[anchor:pin_html.index('</table>', anchor)]
ports = {}
for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.S):
    cells = [html.unescape(re.sub('<[^>]+>', '', x)).strip()
             for x in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)]
    if len(cells) >= 5 and cells[0] != 'Port Name':
        ports[cells[0]] = cells[2].split('/')[0]
assert ports and ports == baseline['pins'], 'Public pins changed'
image = PNR/(NAME+'.fs')
for name in inputs:
    assert (ROOT/name).stat().st_mtime <= image.stat().st_mtime, 'Source newer than image: '+name
target = ROOT/'build/soundcore_headphone_expression_20261028.fs'
if target.exists():
    assert sha(target) == sha(image), 'Refuse to overwrite different published candidate'
else:
    shutil.copy2(image, target)
for source, dest in [(NAME+'.rpt.txt', 'resource_report.txt'),
                     (NAME+'_tr_content.html', 'timing_report.html'),
                     (NAME+'.pin.html', 'pin_report.html')]:
    shutil.copy2(PNR/source, OUT/dest)
code = re.search(r'//UserCode:\s*(\S+)', target.read_text())[1]
evidence = ['tests.json', 'profile_validation.json', 'spectral_validation.json',
            'texture_levels_rom.csv', 'audition.json', 'audition.log', 'audition_controls.csv', 'audio_validation.json',
            'resource_report.txt', 'timing_report.html', 'pin_report.html',
            'gowin_rom_build.log', 'coefficient_reference.json']
evidence += [t['test']+'.log' for t in tests]
result = {
    **data, 'firmware': str(target), 'sha256': sha(target), 'user_code': code,
    'resources': resources,
    'baseline': {k: baseline[k] for k in ['firmware', 'sha256', 'user_code', 'resources']},
    'saved_expression_profile': profile, 'saved_pressure_profile': baseline['saved_profile'],
    'manual_calibration_each_boot': False, 'automatic_zero_samples_per_pad': 16,
    'attack_strength_hold_frames': 1920, 'attack_strength_hold_ms': 40,
    'attack_hold_is_added_onset_latency': False,
    'independent_voices': 32, 'nominal_sample_rate_hz': 48000,
    'audio_frame_clocks': 256, 'audio_completion_clocks': 225,
    'audio_clock_hz': 12288000, 'frame_margin_clocks': 31,
    'default_paths_unchanged': True, 'disabled_pcm_bitexact_frames': 1400,
    'rom_lut_bitexact_combinations': 17920, 'unrelated_voice_contributions_checked': 5580,
    'expression_mode': 'opt-in dedicated full headphone top; early pressure enabled',
    'phone_expression': 'initial note strength; no new continuous-pressure BLE protocol',
    'offline_expression': 'fixed 176 through the new texture; song events unchanged',
    'coefficient_storage': 'synchronous dual-read on-chip parameter ROM; not PCM samples',
    'tests': tests, 'spectral_validation': spectral, 'audition': audition,
    'protected_files_unchanged': len(protected), 'pins': ports, 'pins_unchanged': True,
    'changed_existing_product_sources': changed, 'source_sha256': inputs,
    'sram_written': False, 'flash_written': False, 'hardware_scan_performed': False,
    'real_instrument_calibration_performed': False, 'physical_listening_verified': False,
    'end_to_end_latency_measured': False, 'global_32_voice_clip_free_claim': False,
    'evidence_sha256': {name: sha(OUT/name) for name in evidence},
    'preview_sha256': {Path(p).name: sha(Path(p)) for p in audition['preview_files'].values()}}
(OUT/'release.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: result[k] for k in ['firmware', 'user_code', 'resources',
      'setup_slack_ns', 'hold_slack_ns', 'protected_files_unchanged']}, ensure_ascii=False, indent=2))
