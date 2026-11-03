"""Confirm a completed Flash write after the board's configuration delay."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/speaker_led8_20261031'
BUILD = ROOT / 'build/speaker_led8_20261031'
CLI = 'D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
record_path = BUILD / 'programming_latest_flash.json'
record = json.loads(record_path.read_text(encoding='utf-8'))
logs = Path(record['logs'][0]['path']).parent
release = json.loads((OUT / 'release.json').read_text(encoding='utf-8'))
assert record['flash_written'] and record['flash_verified']
assert record['expected_user_code'] == release['user_code'] == '0x000005D8'
assert hashlib.sha256(Path(record['firmware']).read_bytes()).hexdigest() == record['sha256'] == release['sha256']


def save():
    body = json.dumps(record, ensure_ascii=False, indent=2)
    (logs / 'programming_flash.json').write_text(body, encoding='utf-8')
    record_path.write_text(body, encoding='utf-8')


def run(name, args):
    command = [CLI, *args]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, cwd=logs)
    body = proc.stdout.decode('utf-8', errors='replace')
    path = logs / (name + '.log')
    path.write_text(body, encoding='utf-8')
    record['logs'].append({'path': str(path), 'command': command, 'exit_code': proc.returncode})
    save()
    assert proc.returncode == 0 and 'Finished.' in body, name
    return body


run('reload_confirm', ['--device', 'GW5AT-60B', '--operation_index', '1'])
record['reloaded_from_flash'] = True
save()
for attempt in range(1, 7):
    time.sleep(4)
    body = run(f'codes_delayed_{attempt}', ['--device', 'GW5AT-60B', '--operation_index', '0'])
    code = re.search(r'User Code is:\s*(0x[0-9A-Fa-f]+)', body).group(1)
    status = re.search(r'Status Code is:\s*(0x[0-9A-Fa-f]+)', body).group(1)
    print(f'after reload attempt {attempt}: user={code} status={status}', flush=True)
    if '0x0001481B' in body and int(code, 16) == int(release['user_code'], 16) and status == '0x70026020':
        record.update(user_code=code, status_code=status, readback_matched=True,
                      configuration_delay_seconds=4 * attempt)
        record.pop('error', None)
        save()
        break
else:
    raise RuntimeError('Flash reload never reached expected UserCode and normal status')

shutil.copyfile(logs / 'programming_flash.json', OUT / 'programming_flash.json')
release.update(status='flash_programmed_physical_acceptance_pending', flash_written=True,
               flash_verified=True, reloaded_from_flash=True, readback_matched=True,
               programming_flash_record=str(logs / 'programming_flash.json'))
(OUT / 'release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf-8')
pointer_path = ROOT / 'build/latest_product_firmware.json'
pointer = json.loads(pointer_path.read_text(encoding='utf-8'))
pointer.update(status='flash_programmed_physical_acceptance_pending', flash_written=True,
               flash_verified=True, reloaded_from_flash=True, user_code=record['user_code'],
               flash_record=str(logs / 'programming_flash.json'))
pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in OUT.rglob('*') if p.is_file() and p.name != 'SHA256.json'},
                                    ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'flash_verified': True, 'reloaded_from_flash': True,
                  'user_code': record['user_code'], 'status_code': record['status_code'],
                  'record': str(logs / 'programming_flash.json')}, ensure_ascii=False), flush=True)
