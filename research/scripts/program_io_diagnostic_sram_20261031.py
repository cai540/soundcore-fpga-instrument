"""Load a verified temporary input/OLED diagnostic into SRAM."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--release-dir',default='build/io_diagnostic_20261031')
args=parser.parse_args()
OUT=(ROOT/args.release_dir).resolve()
assert OUT.parent==ROOT/'build' and OUT.name in ['io_diagnostic_20261031','io_all_pixels_20261031','oled_hardware_selftest_20261031','oled_internal_iref_20261031']
release=json.loads((OUT/'release.json').read_text(encoding='utf-8'))
firmware=Path(release['firmware'])
assert release['diagnostic_only']
if OUT.name=='io_diagnostic_20261031':assert release['user_code']=='0x0000FF9B'
elif OUT.name=='io_all_pixels_20261031':assert release['display_test']=='all_pixels_A5'
else:
    assert release['display_test']=='oled_hardware_selftest'
    tests=json.loads((OUT/'tests.json').read_text(encoding='utf-8'))
    assert len(tests)==8 and all(t['passed']for t in tests)
assert hashlib.sha256(firmware.read_bytes()).hexdigest()==release['sha256']
assert release['pins_verified']==29 and not any(release['violations'].values())
CLI='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
logs=OUT/('programming_'+stamp);logs.mkdir()
record={'time':datetime.datetime.now().astimezone().isoformat(),'firmware':str(firmware),
        'sha256':release['sha256'],'expected_user_code':release['user_code'],
        'diagnostic_only':True,'operation_index':2,'flash_written':False,'sram_written':False,'logs':[]}


def save():
    body=json.dumps(record,ensure_ascii=False,indent=2)
    (logs/'programming_sram.json').write_text(body,encoding='utf-8')
    (OUT/'programming_latest_sram.json').write_text(body,encoding='utf-8')


def run(name,args):
    command=[CLI,*args]
    proc=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
    body=proc.stdout.decode('utf-8',errors='replace')
    path=logs/(name+'.log');path.write_text(body,encoding='utf-8')
    record['logs'].append({'path':str(path),'exit_code':proc.returncode,'command':command});save()
    assert proc.returncode==0,(name,body)
    return body


try:
    scan=run('scan',['--scan'])
    assert re.search(r'\b1 device\(s\) found',scan) and 'GW5AT-60B'in scan and '0x0001481B'in scan
    before=run('before',['--device','GW5AT-60B','--operation_index','0'])
    record['previous_user_code']=re.search(r'User Code is:\s*(0x[\dA-Fa-f]+)',before).group(1);save()
    print('Before='+record['previous_user_code']+'; downloading diagnostic SRAM',flush=True)
    result=run('program_sram',['--device','GW5AT-60B','--operation_index','2','--fsFile',str(firmware)])
    assert 'SRAM Program'in result and 'Finished.'in result
    record['sram_written']=True;save()
    after=run('readback',['--device','GW5AT-60B','--operation_index','0'])
    code=re.search(r'User Code is:\s*(0x[\dA-Fa-f]+)',after).group(1)
    status=re.search(r'Status Code is:\s*(0x[\dA-Fa-f]+)',after).group(1)
    assert '0x0001481B'in after and int(code,16)==int(release['user_code'],16) and status=='0x70026020'
    record.update(user_code=code,status_code=status,readback_matched=True);save()
except Exception as error:
    record['error']=repr(error);save();raise

release.update(sram_written=True,readback_matched=True,programming_record=str(logs/'programming_sram.json'))
(OUT/'release.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
pointer_path=ROOT/'build/latest_product_firmware.json'
pointer=json.loads(pointer_path.read_text(encoding='utf-8'))
runtime={'kind':'temporary_io_diagnostic','user_code':code,'status_code':status,
         'record':str(logs/'programming_sram.json'),'restore_full_product_release':pointer['release_dir'],
         'display_test':release.get('display_test','status_text'),
         'internal_iref':release.get('internal_iref',False),
         'flash_user_code':pointer.get('last_flash_user_code','0x000005D8')}
pointer['current_runtime_override']=runtime
pointer_path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'build/current_board_runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'diagnostic_sram_programmed':True,'user_code':code,'status':status,'flash_written':False}),flush=True)
