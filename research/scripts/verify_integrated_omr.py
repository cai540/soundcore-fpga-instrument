"""Exercise the actual copied product BLE endpoint and OMR core together."""
from pathlib import Path
import re,subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'build/fpga_omr_20261031';sim=out/'simulation'
sys.path.insert(0,str(ROOT))
from fpga_omr.protocol import frame
endpoint=out/'baseline/rtl/ble_control_endpoint.v';source=endpoint.read_text(encoding='utf8')
header=source[:source.index(');')]
inputs=re.findall(r'input wire(?:\s+\[[^\]]+\])?\s+(\w+)',header)
values={'clk':'clk','rst_n':'rst_n','rx_valid':'rx_valid','rx_byte':'rx_byte','tx_ready':'tx_ready','write_enable':"1'b1"}
ports=[f'.{n}({values.get(n,"\'0")})'for n in inputs]
ports+=['.tx_valid(tx_valid)','.tx_byte(tx_byte)','.remote_valid(remote_valid)','.remote_type(remote_type)']
instance="ble_control_endpoint #(.EXTENDED_STATE(1),.REALTIME_NOTES(1),.OMR_ENABLE(1)) dut("+','.join(ports)+');'
tb=(sim/'tb_protocol.v').read_text()
tb=re.sub(r'omr_serial_endpoint #\(.*?\) dut\(.*?\);',lambda _:instance,tb,count=1)
tb=re.sub(r' // Damaged CRC.*?\n send_request', '\n send_request',tb,flags=re.S)
assert 'Damaged CRC'not in tb
request=sim/'requests.hex';base=request.read_text();original_count=len(base.splitlines())
extra=frame(1,10)
combined=sim/'integrated_requests.hex';combined.write_text(base+''.join(f'{b:02x}\n'for b in extra))
tb=tb.replace(str(request.as_posix()),str(combined.as_posix()))
tb=tb.replace(f'request[0:{original_count-1}]',f'request[0:{original_count+len(extra)-1}]')
tb=tb.replace('reply[2]!=224','reply[2]!=(seq==10?128:224)')
tb=tb.replace(' $display("PASS byte framing',f' send_request({original_count},{len(extra)},10,0);\n $display("PASS legacy GET_STATE after OMR plus byte framing')
tb=tb.replace('integer received=0,ticks=0;','integer received=0,ticks=0,live_count=0;wire remote_valid;wire[7:0]remote_type;')
tb=tb.replace('ticks<=ticks+1;','ticks<=ticks+1;if(remote_valid&&remote_type==8\'h24)live_count=live_count+1;')
live=frame(0x24,200,bytes([1,1,80]))
cases=''.join(f'{100+i}:begin rx_valid=1;rx_byte=8\'h{b:02x};end 'for i,b in enumerate(live))
tb=tb.replace('timeout=timeout+1;end',f'timeout=timeout+1;if(seq==8)case(timeout){cases}default:rx_valid=0;endcase end')
tb=tb.replace('if(status==1&&','if(seq==8&&live_count!=1)$fatal(1,"Realtime note was blocked by OMR");\n if(status==1&&')
tb=tb.replace('PASS legacy GET_STATE','PASS realtime note during inference and legacy GET_STATE')
(sim/'tb_integrated.v').write_text(tb,encoding='ascii')
iverilog=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe')
files=[ROOT/'rtl/omr_symbol_mlp.v',ROOT/'rtl/omr_frame_endpoint.v',ROOT/'rtl/ble_frame_parser.v',endpoint,sim/'tb_integrated.v']
p=subprocess.run([str(iverilog),'-g2012','-s','tb','-o',str(sim/'integrated.vvp'),*map(str,files)],capture_output=True,text=True,cwd=ROOT)
(sim/'integrated_compile.log').write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0,p.stderr[-1600:]
p=subprocess.run([str(iverilog.with_name('vvp.exe')),str(sim/'integrated.vvp')],capture_output=True,text=True,cwd=ROOT)
(sim/'integrated.log').write_text(p.stdout+p.stderr,encoding='utf8');print(p.stdout[-1000:]);assert p.returncode==0 and'PASS'in p.stdout
