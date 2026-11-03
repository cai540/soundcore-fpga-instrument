"""Controlled SRAM rollback to the exact 358D image read before today's Flash write."""
from pathlib import Path
import datetime,hashlib,json,re,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'build/soundcore_oled_lyric_sync_20261026.fs'
expected_sha='fd686d2879a50c7261096e583f5acfecebc0ddbfb5b4d5cc68056233cba58db7'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected_sha
header=source.read_bytes()[:1600].decode('ascii',errors='replace')
assert '0x0000358D'in header and 'GW5AT-60B-PBGA484A'in header
original=json.loads((ROOT/'build/oled_lyric_sync_programming_20261026.json').read_text(encoding='utf-8'))
assert original['artifacts']['fpga']['sha256']==expected_sha and original['user_code']=='0x0000358D'
CLI='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
OUT=ROOT/'build/pre_flash_baseline_358d_20261031';OUT.mkdir(exist_ok=True)
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');logs=OUT/('programming_'+stamp);logs.mkdir()
record={'time':datetime.datetime.now().astimezone().isoformat(),'firmware':str(source),'sha256':expected_sha,
        'expected_user_code':'0x0000358D','operation_index':2,'flash_written':False,
        'sram_written':False,'cold_power_cycle_confirmed_by_user':True,'logs':[]}

def save():
    body=json.dumps(record,ensure_ascii=False,indent=2)
    (logs/'programming_sram.json').write_text(body,encoding='utf-8')
    (OUT/'programming_latest_sram.json').write_text(body,encoding='utf-8')

def run(name,args):
    command=[CLI,*args]
    p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
    body=p.stdout.decode('utf-8',errors='replace');path=logs/(name+'.log');path.write_text(body,encoding='utf-8')
    record['logs'].append({'path':str(path),'exit_code':p.returncode,'command':command});save()
    assert p.returncode==0,(name,body)
    return body

try:
    scan=run('scan',['--scan'])
    assert re.search(r'\b1 device\(s\) found',scan) and 'GW5AT-60B'in scan and '0x0001481B'in scan
    for attempt in range(6):
        before=run(f'before_{attempt}',['--device','GW5AT-60B','--operation_index','0'])
        previous=re.search(r'User Code is:\s*(0x[\dA-Fa-f]+)',before).group(1)
        if int(previous,16)==0x5d8:break
        if int(previous,16)!=0:raise RuntimeError('Expected 05D8 after confirmed cold boot, got '+previous)
        time.sleep(2)
    else:raise RuntimeError('Flash configuration did not finish')
    record['previous_user_code']=previous;save()
    print('Cold-boot baseline='+previous+'; loading original 358D into SRAM',flush=True)
    programmed=run('program_sram',['--device','GW5AT-60B','--operation_index','2','--fsFile',str(source)])
    assert 'SRAM Program'in programmed and 'Finished.'in programmed
    record['sram_written']=True;save()
    after=run('readback',['--device','GW5AT-60B','--operation_index','0'])
    code=re.search(r'User Code is:\s*(0x[\dA-Fa-f]+)',after).group(1)
    status=re.search(r'Status Code is:\s*(0x[\dA-Fa-f]+)',after).group(1)
    assert int(code,16)==0x358d and status=='0x70026020' and '0x0001481B'in after
    record.update(user_code=code,status_code=status,readback_matched=True);save()
except Exception as error:
    record['error']=repr(error);save();raise

runtime={'kind':'pre_flash_baseline_sram_ab_test','user_code':code,'status_code':status,
         'record':str(logs/'programming_sram.json'),'flash_user_code':'0x000005D8',
         'cold_power_cycle_confirmed_by_user':True,'physical_oled_result':'pending'}
(ROOT/'build/current_board_runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
pointer_path=ROOT/'build/latest_product_firmware.json';pointer=json.loads(pointer_path.read_text(encoding='utf-8'))
pointer['current_runtime_override']=runtime
pointer_path.write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sram_rollback_finished':True,'user_code':code,'status_code':status,'flash_written':False}),flush=True)
