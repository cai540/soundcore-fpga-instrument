"""Write the gated current speaker image to external Flash, verify, reload, read codes."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--release-dir', default='output/speaker_led8_20261031')
parser.add_argument('--prepare-only', action='store_true', help='Validate the release without accessing hardware')
args = parser.parse_args()
OUT = ROOT / args.release_dir
BUILD = ROOT / 'build' / OUT.name
CLI = Path('D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe')
release = json.loads((OUT / 'release.json').read_text(encoding='utf-8'))
source = Path(release['firmware'])
assert source.resolve().parent == OUT.resolve()
assert release.get('programming_allowed', True), 'Release is not approved for programming'
assert re.fullmatch(r'0x[0-9A-Fa-f]{8}', release['user_code'])
assert release['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
assert release['standard_i2s_selected'] and release['routed_pins_verified']
assert len(release['tests']) == 7 and all(t['passed'] for t in release['tests'])
assert not any(release['violations'].values())
assert release['led_positions'] == ['A8', 'B8', 'A9', 'B9', 'B11', 'A12', 'B12']
if release.get('panel_menu_fix'):
    panel_tests = release['panel_menu_tests']
    assert len(panel_tests) == (11 if release.get('panel_native_transport') else 9)
    assert all(t['passed'] for t in panel_tests)
    assert 'tb_panel_oled_menu_flow' in {t['test'] for t in panel_tests}
    if release.get('panel_native_transport'):
        assert {'tb_native_panel_transport', 'tb_native_panel_oled_flow', 'tb_native_demo_audio'} <= {t['test'] for t in panel_tests}
if release.get('k5_lamp_follow'):
    assert release['lamp_tests'] and all(t['passed'] for t in release['lamp_tests'])
if release.get('lamp_drive_ma'):
    assert release['lamp_drive_report_verified'] and release['lamp_electrical_check']['candidate_resistor_bound_ma_at_3v465'] < release['lamp_drive_ma']
if args.prepare_only:
    print(json.dumps({'prepared_only': True, 'hardware_accessed': False, 'flash_written': False,
                      'firmware': str(source), 'sha256': release['sha256'],
                      'expected_user_code': release['user_code'], 'operation_index': 69},
                     ensure_ascii=False), flush=True)
    raise SystemExit(0)

pointer_path = ROOT / 'build/latest_product_firmware.json'
previous_pointer = json.loads(pointer_path.read_text(encoding='utf-8')) if pointer_path.exists() else {}

stamp = datetime.datetime.now().astimezone().strftime('%Y%m%d_%H%M%S')
logs = BUILD / ('flash_programming_' + stamp)
logs.mkdir(parents=True)
image = logs / 'speaker_led8_flash.fs'
shutil.copyfile(source, image)
record = {
    'time': datetime.datetime.now().astimezone().isoformat(),
    'device': 'GW5AT-60B', 'device_id': '0x0001481B',
    'firmware': str(source), 'sha256': release['sha256'],
    'expected_user_code': release['user_code'],
    'operation_index': 69, 'flash_written': False,
    'flash_verified': False, 'reloaded_from_flash': False,
    'readback_matched': False, 'physical_audio_verified': False,
    'logs': [],
}


def save():
    body = json.dumps(record, ensure_ascii=False, indent=2)
    (logs / 'programming_flash.json').write_text(body, encoding='utf-8')
    (BUILD / 'programming_latest_flash.json').write_text(body, encoding='utf-8')


def run(name, args, timeout=60):
    command = [str(CLI), *args]
    print(name + ': starting', flush=True)
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout, cwd=logs)
    body = proc.stdout.decode('utf-8', errors='replace')
    path = logs / (name + '.log')
    path.write_text(body, encoding='utf-8')
    record['logs'].append({'path': str(path), 'command': command, 'exit_code': proc.returncode})
    save()
    print(name + ': exit=' + str(proc.returncode) + ' tail=' + body[-350:].replace('\r', ' '), flush=True)
    if proc.returncode != 0:
        raise RuntimeError(name + ' failed')
    return body


save()
try:
    scan = run('scan', ['--scan'])
    assert re.search(r'\b1 device\(s\) found', scan)
    assert 'GW5AT-60B' in scan and '0x0001481B' in scan
    before = run('codes_before', ['--device', 'GW5AT-60B', '--operation_index', '0'])
    record['previous_user_code'] = re.search(r'User Code is:\s*(0x[0-9A-Fa-f]+)', before).group(1)
    save()
    written = run('program_flash', ['--device', 'GW5AT-60B', '--operation_index', '69',
                                    '--fsFile', str(image)], timeout=1500)
    assert 'Program and Verify flash successfully' in written and 'Finished.' in written
    record['flash_written'] = True
    record['flash_verified'] = True
    save()
    loaded = run('reload_from_flash', ['--device', 'GW5AT-60B', '--operation_index', '1'])
    assert 'Finished.' in loaded
    record['reloaded_from_flash'] = True
    save()
    for attempt in range(1, 7):
        time.sleep(4)
        after = run(f'codes_after_{attempt}', ['--device', 'GW5AT-60B', '--operation_index', '0'])
        record['user_code'] = re.search(r'User Code is:\s*(0x[0-9A-Fa-f]+)', after).group(1)
        record['status_code'] = re.search(r'Status Code is:\s*(0x[0-9A-Fa-f]+)', after).group(1)
        if ('0x0001481B' in after and int(record['user_code'], 16) == int(release['user_code'], 16)
                and record['status_code'] == '0x70026020'):
            record['readback_matched'] = True
            record['configuration_delay_seconds'] = 4 * attempt
            save()
            break
    else:
        raise RuntimeError('Flash reload never reached expected UserCode and normal status')
except Exception as exc:
    record['error'] = str(exc)
    save()
    raise

shutil.copyfile(logs / 'programming_flash.json', OUT / 'programming_flash.json')
release.update(status='flash_programmed_physical_acceptance_pending', flash_written=True,
               flash_verified=True, reloaded_from_flash=True, readback_matched=True,
               programming_flash_record=str(logs / 'programming_flash.json'))
(OUT / 'release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf-8')
pointer = previous_pointer.copy()
if previous_pointer.get('flash_written'):
    old_flash = {key: previous_pointer.get(key) for key in ['firmware', 'user_code', 'flash_record']}
else:
    old_flash = {'firmware': previous_pointer.get('last_flash_firmware'),
                 'user_code': previous_pointer.get('last_flash_user_code'),
                 'flash_record': previous_pointer.get('last_flash_record')}
pointer.update(firmware=str(source), sha256=release['sha256'], release_dir=str(OUT),
               status='flash_programmed_physical_acceptance_pending', flash_written=True,
               flash_verified=True, reloaded_from_flash=True,
               readback_matched=True, user_code=record['user_code'],
               flash_record=str(logs / 'programming_flash.json'), record=str(logs / 'programming_flash.json'),
               previous_flash=old_flash, last_flash_firmware=str(source),
               last_flash_user_code=record['user_code'], last_flash_record=str(logs / 'programming_flash.json'))
for key in ['audio_path', 'startup_volume', 'model_crc32', 'led_positions', 'pressure_profile_id',
            'calibrated_input_scale_q12', 'k5_lamp_follow', 'panel_native_transport', 'lamp_control_position',
            'lamp_ground_position', 'lamp_physical_verified', 'lamp_temporary_series_resistor_ohm', 'apk']:
    if key in release:
        pointer[key] = release[key]
pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / 'build/current_board_runtime.json').write_text(json.dumps({
    'kind': 'full_product_flash', 'user_code': record['user_code'],
    'flash_user_code': record['user_code'], 'record': str(logs / 'programming_flash.json'),
    'readback_matched': True, 'physical_lamp_verified': False}, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256.json'},
                                    ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'flash_verified': True, 'reloaded_from_flash': True,
                  'user_code': record['user_code'], 'record': str(logs / 'programming_flash.json')},
                 ensure_ascii=False), flush=True)
