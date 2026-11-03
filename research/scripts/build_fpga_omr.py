"""Freeze sources and build native Gowin standalone/instrument candidates, no programming."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/fpga_omr_20261031';MODEL=OUT/'model'
TOOL=Path('D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')
manifest=json.loads((MODEL/'manifest.json').read_text(encoding='utf8'))
if 'model_crc32' not in manifest:raise RuntimeError('Verify the integer model before building')
SRC=OUT/'src';SRC.mkdir(parents=True,exist_ok=True)
new_files=['omr_symbol_mlp.v','omr_frame_endpoint.v','omr_serial_endpoint.v','ble_frame_parser.v','uart_8n1_9600.v']
for name in new_files:shutil.copyfile(ROOT/'rtl'/name,SRC/name)
params=','.join(f'.{key.upper()}_FILE("{(MODEL/(key+".hex")).as_posix()}")'for key in ['w1','b1','w2','b2'])+f',.SHIFT1({manifest["shift1"]}),.MODEL_CRC(32\'h{manifest["model_crc32"]:08x})'
(SRC/'omr_uart_top.v').write_text(f'''module omr_uart_top(input wire sys_clk,input wire rst_n,input wire ble_uart_rx,output wire ble_uart_tx);
wire rv,tv,tr;wire[7:0]rb,tb;
uart_8n1_9600 #(.CLKS_PER_BIT(5208)) uart(.clk(sys_clk),.rst_n(rst_n),.rx(ble_uart_rx),.rx_valid(rv),.rx_byte(rb),.tx(ble_uart_tx),.tx_valid(tv),.tx_byte(tb),.tx_ready(tr));
omr_serial_endpoint #({params}) endpoint(.clk(sys_clk),.rst_n(rst_n),.rx_valid(rv),.rx_byte(rb),.tx_valid(tv),.tx_byte(tb),.tx_ready(tr));
endmodule
''',encoding='ascii')

def project(folder,name,top,files,cst,sdc):
    folder.mkdir(parents=True,exist_ok=True);root=ET.Element('Project')
    ET.SubElement(root,'Template').text='FPGA';ET.SubElement(root,'Version').text='5'
    ET.SubElement(root,'Device',name='GW5AT-60B',pn='GW5AT-LV60PG484AC1/I0').text='gw5at60b-002'
    fl=ET.SubElement(root,'FileList')
    for p,kind in [*( (p,'file.verilog')for p in files),(cst,'file.cst'),(sdc,'file.sdc')]:ET.SubElement(fl,'File',path=p.as_posix(),type=kind,enable='1')
    path=folder/(name+'.gprj');ET.ElementTree(root).write(path,encoding='utf8',xml_declaration=True)
    tcl=folder/'build.tcl';tcl.write_text(f'open_project {{{path.as_posix()}}}\nset_option -top_module {top}\nrun all\n',encoding='utf8')
    return tcl

def standalone():
    folder=OUT/'gowin_standalone';folder.mkdir(exist_ok=True)
    cst=folder/'pins.cst';cst.write_text('\n'.join(s for s in (ROOT/'board/soundcore_headphone_60k.cst').read_text().splitlines()if any('"'+n+'"'in s for n in ['sys_clk','rst_n','ble_uart_rx','ble_uart_tx']))+'\n')
    sdc=folder/'clock.sdc';sdc.write_text('create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]\n')
    return project(folder,'omr_uart_60k','omr_uart_top',[SRC/n for n in [*new_files,'omr_uart_top.v']],cst,sdc)

def integrated():
    frozen=ROOT/'output/melody_workbench_20261028/source';snapshot=OUT/'baseline';snapshot.mkdir(exist_ok=True)
    old=ET.parse(frozen/'build/gowin_final/soundcore_workbench_60k.gprj')
    original_files=[];copied={}
    def copy_source(rel):
        if rel in copied:return copied[rel]
        source=frozen/rel
        if not source.exists():raise RuntimeError('Frozen baseline input missing: '+str(rel))
        target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix.lower()in ('.v','.vh','.cst','.sdc'):
            text=source.read_text(encoding='utf8')
            for include in re.findall(r'`include\s+"([^"]+)"',text):
                p=Path(include)
                relative=p.relative_to(ROOT)if p.is_absolute()else (rel.parent/p)
                include_target=copy_source(relative)
                text=text.replace('"'+include+'"','"'+include_target.as_posix()+'"')
            target.write_text(text,encoding='utf8')
        else:shutil.copyfile(source,target)
        copied[rel]=target;return target
    for item in old.findall('./FileList/File'):
        if item.attrib.get('enable')!='1':continue
        rel=Path(item.attrib['path']).relative_to(ROOT);target=copy_source(rel)
        if item.attrib['type']=='file.verilog':original_files.append(target)
    endpoint=snapshot/'rtl/ble_control_endpoint.v';text=endpoint.read_text(encoding='utf8')
    text=text.replace('parameter CAPTURE_UI = 0','parameter CAPTURE_UI = 0,\n    parameter OMR_ENABLE = 0')
    text=text.replace('SCORE_WAIT=4;','SCORE_WAIT=4, OMR_WAIT=5;')
    marker='    always @(posedge clk or negedge rst_n) begin'
    instance=f'''    wire omr_response_valid;wire [111:0] omr_response_payload;
    omr_frame_endpoint #({params}) omr(
      .clk(clk),.rst_n(rst_n),.request_valid(OMR_ENABLE!=0 && phase==IDLE && frame_valid && frame_type>=8'h60 && frame_type<=8'h63),
      .request_type(frame_type),.request_length(frame_len),.request_payload(frame_payload),
      .response_valid(omr_response_valid),.response_payload(omr_response_payload));
'''
    assert text.count(marker)==1;text=text.replace(marker,instance+marker)
    marker='end else if(CAPTURE_UI!=0 &&'
    assert text.count(marker)==1
    text=text.replace(marker,"end else if(OMR_ENABLE!=0 && frame_type>=8'h60 && frame_type<=8'h63)begin\n                        response_error<=0;score_wait_count<=0;phase<=OMR_WAIT;\n                    "+marker)
    marker='                SCORE_WAIT:begin'
    assert text.count(marker)==1
    text=text.replace(marker,"                OMR_WAIT:begin\n                    if(omr_response_valid)begin\n                        snapshot<=omr_response_payload;response_type<=8'he0;response_len<=14;\n                        response_crc<=crc_response(8'he0,response_seq,omr_response_payload,14);phase<=SEND;\n                    end else if(score_wait_count==16'hffff)begin\n                        response_error<=1;error_code<=5;response_crc<=crc_error(response_seq,5);phase<=SEND;\n                    end else score_wait_count<=score_wait_count+1'b1;\n                end\n"+marker)
    endpoint.write_text(text,encoding='utf8')
    top=snapshot/'board/pressure_i2s_panel_oled_ble_experiment_top.v';text=top.read_text(encoding='utf8')
    marker='.CAPTURE_UI(UPLOADED_SCORE_ENABLE))';assert text.count(marker)==1
    top.write_text(text.replace(marker,'.CAPTURE_UI(UPLOADED_SCORE_ENABLE),.OMR_ENABLE(1))'),encoding='utf8')
    hashes={str(p.relative_to(snapshot)):hashlib.sha256(p.read_bytes()).hexdigest()for p in copied.values()}
    (OUT/'baseline_sources.json').write_text(json.dumps({'baseline':'output/melody_workbench_20261028/source','only_modified_baseline_files':['rtl/ble_control_endpoint.v','board/pressure_i2s_panel_oled_ble_experiment_top.v'],'snapshot_sha256':hashes},indent=2))
    return project(OUT/'gowin_integrated','soundcore_omr_60k','soundcore_melody_top',original_files+[SRC/n for n in new_files[:2]],snapshot/'board/soundcore_headphone_60k.cst',snapshot/'board/tang_mega_60k.sdc')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['standalone','integrated']);args=ap.parse_args()
    tcl=standalone()if args.mode=='standalone'else integrated()
    with (tcl.parent/'tool.log').open('w',encoding='utf8')as log:p=subprocess.run([str(TOOL),str(tcl)],cwd=tcl.parent,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps({'mode':args.mode,'tool_exit_code':p.returncode,'log':str(tcl.parent/'tool.log')}),flush=True)
    if p.returncode:sys.exit(p.returncode)
