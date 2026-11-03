"""Program only the gated speaker image into the single matching FPGA's SRAM."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--release-dir')
args=parser.parse_args()
pointer=ROOT/'build/latest_product_firmware.json'
previous_pointer=json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else {}
if args.release_dir:
    OUT=ROOT/args.release_dir
elif pointer.exists():
    OUT=Path(json.loads(pointer.read_text(encoding='utf-8'))['firmware']).parent
else:
    OUT=ROOT/'output/speaker_omr_20261031'
BUILD=ROOT/'build'/OUT.name
release=json.loads((OUT/'release.json').read_text(encoding='utf-8'))
assert release.get('programming_allowed',True), 'Rejected image; inspect release status'
candidate_already_in_flash=bool(release.get('flash_written') and release.get('flash_verified'))
assert release['standard_i2s_selected'] and release['routed_pins_verified']
assert len(release['tests'])==(7 if release.get('uniform_pad_velocity') else 4)
assert all(t['passed']for t in release['tests']) and not any(release['violations'].values())
if release.get('panel_menu_fix'):
    menu_tests=release['panel_menu_tests']
    assert len(menu_tests)==(11 if release.get('panel_native_transport') else 9) and all(t['passed']for t in menu_tests)
    assert 'tb_panel_oled_menu_flow' in {t['test']for t in menu_tests}
    if release.get('panel_native_transport'):
        assert {'tb_native_panel_transport','tb_native_panel_oled_flow','tb_native_demo_audio'} <= {t['test']for t in menu_tests}
if release.get('k5_lamp_follow'):
    assert release['lamp_tests'] and all(t['passed']for t in release['lamp_tests'])
if release.get('lamp_drive_ma'):
    assert release['lamp_drive_report_verified'] and release['lamp_electrical_check']['candidate_resistor_bound_ma_at_3v465'] < release['lamp_drive_ma']
source=Path(release['firmware']);assert hashlib.sha256(source.read_bytes()).hexdigest()==release['sha256']
stamp=datetime.datetime.now().astimezone().strftime('%Y%m%d_%H%M%S');logs=BUILD/('programming_'+stamp);logs.mkdir()
image=logs/'speaker_omr_sram.fs';shutil.copyfile(source,image)
cli='D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/Programmer/bin/programmer_cli.exe'
record={'time':datetime.datetime.now().astimezone().isoformat(),'device':'GW5AT-60B','device_id':'0x0001481B',
        'firmware':str(source),'sha256':release['sha256'],'expected_user_code':release['user_code'],
        'audio_path':'MAX98357A_standard_I2S','startup_volume':6,'operation_index':2,
        'flash_written':False,'sram_program_finished':False,'readback_matched':False,'physical_audio_verified':False,'logs':[]}
record['lamp_drive_ma']=release.get('lamp_drive_ma',8)
def save():
    text=json.dumps(record,ensure_ascii=False,indent=2)
    (logs/'programming_sram.json').write_text(text,encoding='utf-8')
    (BUILD/'programming_latest_sram.json').write_text(text,encoding='utf-8')
def run(name,args):
    p=subprocess.run([cli,*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
    body=p.stdout.decode('utf-8',errors='replace');path=logs/(name+'.log');path.write_text(body,encoding='utf-8')
    record['logs'].append({'path':str(path),'command':[cli,*args],'exit_code':p.returncode});save()
    print(body,flush=True);assert p.returncode==0,name+' failed';return body
save()
try:
    scan=run('scan',['--scan']);assert re.search(r'\b1 device\(s\) found',scan)and 'GW5AT-60B'in scan and '0x0001481B'in scan
    before=run('codes_before',['--device','GW5AT-60B','--operation_index','0'])
    record['previous_user_code']=re.search(r'User Code is:\s*(0x[0-9A-Fa-f]+)',before).group(1);save()
    result=run('program_sram',['--device','GW5AT-60B','--operation_index','2','--fsFile',str(image)])
    assert 'SRAM Program'in result and 'Finished'in result;record['sram_program_finished']=True;save()
    after=run('codes_after',['--device','GW5AT-60B','--operation_index','0'])
    record['user_code']=re.search(r'User Code is:\s*(0x[0-9A-Fa-f]+)',after).group(1)
    record['status_code']=re.search(r'Status Code is:\s*(0x[0-9A-Fa-f]+)',after).group(1)
    assert int(record['user_code'],16)==int(release['user_code'],16)and '0x0001481B'in after
    record['readback_matched']=True;save()
except Exception as error:
    record['error']=str(error);save();raise
shutil.copyfile(logs/'programming_sram.json',OUT/'programming_sram.json')
release.update(status='sram_programmed_listening_pending',sram_written=True,flash_written=candidate_already_in_flash,
               programming_record=str(logs/'programming_sram.json'),readback_matched=True)
(OUT/'release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
pointer={'firmware':str(source),'sha256':release['sha256'],'user_code':record['user_code'],
         'audio_path':record['audio_path'],'startup_volume':6,'model_crc32':release['model_crc32'],
         'sram_written':True,'flash_written':candidate_already_in_flash,'physical_audio_verified':False,'record':str(logs/'programming_sram.json')}
pointer.update(status='sram_programmed_physical_acceptance_pending',release_dir=str(OUT))
if previous_pointer.get('flash_written'):
    pointer.update(last_flash_firmware=previous_pointer['firmware'],last_flash_user_code=previous_pointer['user_code'],
                   last_flash_record=previous_pointer.get('flash_record'),last_flash_lamp_drive_ma=previous_pointer.get('lamp_drive_ma',8))
else:
    for key in ['last_flash_firmware','last_flash_user_code','last_flash_record','last_flash_lamp_drive_ma']:
        if key in previous_pointer:pointer[key]=previous_pointer[key]
if release.get('led_positions'):
    pointer['led_positions']=release['led_positions']
for key in ['pressure_profile_id','calibrated_input_scale_q12','lamp_drive_ma','lamp_drive_report_verified',
            'lamp_recommended_resistor_ohm','lamp_resistor_change_pending','lamp_control_position',
            'lamp_ground_position','k5_lamp_follow','panel_native_transport','apk']:
    if key in release:pointer[key]=release[key]
(ROOT/'build/latest_product_firmware.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'build/current_board_runtime.json').write_text(json.dumps({'kind':'full_product_sram',
    'user_code':record['user_code'],'record':str(logs/'programming_sram.json'),
    'flash_user_code':pointer.get('last_flash_user_code'),'lamp_drive_ma':record['lamp_drive_ma'],
    'flash_lamp_drive_ma':pointer.get('last_flash_lamp_drive_ma',8)},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'SHA256.json').write_text(json.dumps({str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file()and p.name!='SHA256.json'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sram_program_finished':True,'user_code':record['user_code'],'audio_path':record['audio_path'],'flash_written':False},ensure_ascii=False),flush=True)
