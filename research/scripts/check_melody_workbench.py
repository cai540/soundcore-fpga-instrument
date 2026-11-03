from pathlib import Path
import subprocess,os,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/melody_workbench_20261028'
TOOL=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
os.environ.update(TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'))
project=ET.parse(ROOT/'build/mono_recognition_20261028/gowin/soundcore_melody_60k.gprj')
for m in ['capture_display_state','oled_capture_columns']:
 ET.SubElement(project.find('FileList'),'File',path=(ROOT/'rtl'/(m+'.v')).as_posix(),type='file.verilog',enable='1')
gowin=OUT/'gowin';gowin.mkdir(exist_ok=True);ET.indent(project,space='    ')
project.write(gowin/'soundcore_workbench_60k.gprj',encoding='utf8',xml_declaration=True)
(gowin/'build.tcl').write_text('open_project {'+(gowin/'soundcore_workbench_60k.gprj').as_posix()+'}\nset_option -top_module soundcore_melody_top\nrun all\n',encoding='utf8')
product=(ROOT/'tb/tb_melody_product_integration.v').read_text()
product=product.replace('request(8\'h01,0,0);request', '''request(8'h36,0,0);
  check(dut.control_endpoint.response_type==8'h83,"capture capability ACK");
  payload=0;payload[7:0]=1;payload[15:8]=1;payload[39:24]=120;payload[55:40]=400;payload[79:72]=255;payload[87:80]=160;
  request(8'h37,11,payload);
  check(dut.capture_oled_payload[15:8]==1,"capture summary reaches product OLED");
  request(8'h37,10,payload);
  check(dut.control_endpoint.response_error,"malformed display rejected");
  request(8'h01,0,0);request''')
product=product.replace('check(dut.score_gate &&', 'check(dut.capture_oled_payload[15:8]==10,"device autoplay owns OLED");\n  check(dut.score_gate &&')
product=product.replace('action(4);check', 'action(4);check(dut.capture_oled_payload[15:8]==11,"device guide owns OLED");check')
(OUT/'tb_melody_product_integration.v').write_text(product)
tests={
 'tb_capture_display_state':['capture_display_state'],
 'tb_capture_oled_render':['oled_capture_columns','oled_status_ssd1315','oled_i2c_write2'],
 'tb_capture_oled_i2c':['oled_capture_columns','oled_status_ssd1315','oled_i2c_write2'],
 'tb_melody_product_integration':[],
 'tb_uploaded_song_engine':['uploaded_song_engine'],
 'tb_ble_realtime_endpoint':['ble_control_endpoint','ble_frame_parser'],
 'tb_ble_extended_state':['ble_control_endpoint','ble_frame_parser'],
 'tb_oled_force_geometry':['oled_status_ssd1315','oled_i2c_write2'],
 'tb_oled_product_text':['oled_status_ssd1315','oled_i2c_write2'],
}
results=[]
for name,modules in tests.items():
 source=OUT/(name+'.v') if name=='tb_melody_product_integration' else ROOT/'tb'/(name+'.v')
 if name=='tb_uploaded_song_engine':
  code=source.read_text().replace(' uploaded_song_engine #(',
   ' wire display_receiving;wire [9:0] display_count,display_received,display_expected;\n uploaded_song_engine #(')
  source=OUT/(name+'.v');source.write_text(code)
 cmd=[str(TOOL/'iverilog.exe'),'-g2012','-s',name,'-o',str(OUT/(name+'.vvp')),str(source)]
 if modules:cmd += [str(ROOT/'rtl'/(m+'.v')) for m in modules]
 else:
  for x in project.findall('.//File'):
   if x.get('type')!='file.verilog' or Path(x.get('path')).name=='audio_pll_12m288.v':continue
   p=Path(x.get('path'));s=p.read_text(encoding='utf8');adapt=s.replace('`include "'+ROOT.as_posix()+'/','`include "')
   if adapt!=s:
    mirror=OUT/'sim_sources'/p.relative_to(ROOT);mirror.parent.mkdir(parents=True,exist_ok=True);mirror.write_text(adapt,encoding='utf8');p=mirror
   cmd.append(str(p))
 c=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
 text=c.stdout+c.stderr
 if c.returncode:text+=f'\nCompiler exit: {c.returncode}\n'
 ok=False
 if c.returncode==0:
  r=subprocess.run([str(TOOL/'vvp.exe'),str(OUT/(name+'.vvp'))],cwd=ROOT,capture_output=True,text=True,timeout=180)
  text+=r.stdout+r.stderr;ok=r.returncode==0 and 'PASS:' in text and 'FATAL:' not in text
 (OUT/(name+'.log')).write_text(text,encoding='utf8');print(name,text.strip(),flush=True)
 results.append({'test':name,'passed':ok,'output':text.strip()})
 if not ok:break
(OUT/'rtl_checks.json').write_text(json.dumps(results,indent=2),encoding='utf8')
assert len(results)==len(tests) and all(r['passed'] for r in results)
