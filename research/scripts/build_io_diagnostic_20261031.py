"""Small standalone SRAM diagnostic; never changes the saved full product Flash."""
from pathlib import Path
from lxml import html
import argparse,hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--all-pixels',action='store_true')
mode.add_argument('--oled-selftest',action='store_true')
mode.add_argument('--internal-iref',action='store_true')
args=parser.parse_args()
if args.internal_iref:args.oled_selftest=True
OUT=ROOT/'build'/('oled_internal_iref_20261031'if args.internal_iref else 'oled_hardware_selftest_20261031'if args.oled_selftest else 'io_all_pixels_20261031'if args.all_pixels else 'io_diagnostic_20261031')
SRC=OUT/'src';SRC.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'build/oled_recovery_20261031/baseline'
files=['rtl/oled_i2c_write2.v','rtl/oled_status_ssd1315.v','board/audio_pll_12m288.v','board/soundcore_speaker_omr_60k.cst','board/tang_mega_60k.sdc']
for rel in files:shutil.copyfile(BASE/rel,SRC/Path(rel).name)
if args.all_pixels:
    display=SRC/'oled_status_ssd1315.v'
    text=display.read_text(encoding='utf-8')
    assert text.count("22:init_command=8'hA4;")==1
    display.write_text(text.replace("22:init_command=8'hA4;","22:init_command=8'hA5;"),encoding='utf-8')
    binary=OUT/'all_pixels_test.vvp'
    comp=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012',
        '-s','tb_oled_pin_recovery','-Ptb_oled_pin_recovery.EXPECT_ALL_PIXELS=1','-o',str(binary),
        str(ROOT/'tb/tb_oled_pin_recovery.v'),str(display),str(SRC/'oled_i2c_write2.v')],capture_output=True,text=True,cwd=ROOT)
    assert comp.returncode==0,(comp.returncode,comp.stdout,comp.stderr)
    sim=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe',str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=30)
    assert sim.returncode==0 and 'PASS:'in sim.stdout,sim.stdout+sim.stderr
    (OUT/'all_pixels_test.log').write_text(sim.stdout+sim.stderr,encoding='utf-8')
    print(sim.stdout,flush=True)
top='soundcore_oled_selftest_top'if args.oled_selftest else 'soundcore_io_diagnostic_top'
shutil.copyfile(ROOT/'board'/(top+'.v'),SRC/(top+'.v'))
if args.internal_iref:
    p=SRC/(top+'.v');body=p.read_text(encoding='utf-8')
    assert body.count('parameter integer INTERNAL_IREF=0')==1
    p.write_text(body.replace('parameter integer INTERNAL_IREF=0','parameter integer INTERNAL_IREF=1'),encoding='utf-8')
if args.oled_selftest:
    shutil.copyfile(ROOT/'rtl/oled_hardware_selftest.v',SRC/'oled_hardware_selftest.v')
    tests=[]
    for case in range(8):
        binary=OUT/f'selftest_case{case}.vvp'
        comp=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe','-g2012',
            '-s','tb_oled_hardware_selftest',f'-Ptb_oled_hardware_selftest.CASE_ID={case}',
            f'-Ptb_oled_hardware_selftest.INTERNAL_IREF={int(args.internal_iref)}',
            '-o',str(binary),str(ROOT/'tb/tb_oled_hardware_selftest.v'),str(SRC/'oled_hardware_selftest.v'),
            str(SRC/'oled_i2c_write2.v')],capture_output=True,text=True,cwd=ROOT)
        assert comp.returncode==0,(comp.returncode,comp.stdout,comp.stderr)
        sim=subprocess.run(['D:/FPGA/_Tools/iverilog-conda/Library/bin/vvp.exe',str(binary)],capture_output=True,text=True,cwd=ROOT,timeout=30)
        ok=sim.returncode==0 and 'PASS:'in sim.stdout
        tests.append({'case':case,'passed':ok,'output':sim.stdout+sim.stderr})
        (OUT/'tests.json').write_text(json.dumps(tests,indent=2),encoding='utf-8')
        print(sim.stdout+sim.stderr,flush=True)
        assert ok,case
project=ET.Element('Project');ET.SubElement(project,'Template').text='FPGA';ET.SubElement(project,'Version').text='5'
ET.SubElement(project,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002'
fl=ET.SubElement(project,'FileList')
for p in sorted(SRC.iterdir()):
    ET.SubElement(fl,'File',path=p.as_posix(),type={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}[p.suffix],enable='1')
gprj=OUT/'io_diagnostic.gprj';ET.ElementTree(project).write(gprj,encoding='utf-8',xml_declaration=True)
tcl=OUT/'build.tcl';tcl.write_text(f'open_project {{{gprj.as_posix()}}}\nset_option -top_module {top}\nrun all\n',encoding='utf-8')
with (OUT/'build.log').open('w',encoding='utf-8')as log:
    p=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],stdout=log,stderr=subprocess.STDOUT,cwd=OUT)
assert p.returncode==0,'inspect build.log'
pnr=OUT/'impl/pnr';fs=pnr/'io_diagnostic.fs'
code=re.search(r'UserCode:\s*(0x[0-9a-fA-F]+)',fs.read_bytes()[:1600].decode('ascii',errors='replace')).group(1)
expected=dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);',(SRC/'soundcore_speaker_omr_60k.cst').read_text(encoding='utf-8')))
actual={}
for row in html.fromstring((pnr/'io_diagnostic.pin.html').read_bytes()).xpath('//tr'):
    cells=[c.text_content().strip()for c in row.xpath('./td')]
    if len(cells)>=8 and cells[0]in expected and '/'in cells[2]:actual[cells[0]]=cells[2].split('/')[0]
assert actual==expected,(actual,expected)
timing=html.fromstring((pnr/'io_diagnostic_tr_content.html').read_bytes())
violations={}
for row in timing.xpath('//tr'):
    cells=[' '.join(c.text_content().split())for c in row.xpath('./td')]
    if len(cells)==2 and 'Violated'in cells[0]:violations[cells[0]]=int(cells[1])
assert violations and not any(violations.values())
info={'firmware':str(fs),'sha256':hashlib.sha256(fs.read_bytes()).hexdigest(),'user_code':code,
      'pins_verified':len(actual),'violations':violations,'diagnostic_only':True,
      'display_test':'oled_hardware_selftest'if args.oled_selftest else 'all_pixels_A5'if args.all_pixels else 'status_text',
      'internal_iref':args.internal_iref,
      'leds':{'1-5':'idle,negative_control,address,initialization,pattern_cycle','6':'fault','7':'heartbeat'}if args.oled_selftest else {'1-5':'K1-K5 raw synchronized active-low contacts','6':'OLED full frame ACK ready','7':'heartbeat'},
      'sram_written':False,'flash_written':False}
(OUT/'release.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
print(json.dumps(info),flush=True)
