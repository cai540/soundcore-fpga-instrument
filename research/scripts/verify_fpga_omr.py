"""Generate independent transport vectors and compare every integer logit in RTL."""
from pathlib import Path
import json,subprocess,sys,zlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fpga_omr.protocol import frame
from fpga_omr.model import integer_forward,classify,load_weights

OUT=ROOT/'build/fpga_omr_20261031';MODEL=OUT/'model';SIM=OUT/'simulation';SIM.mkdir(parents=True,exist_ok=True)
IVERILOG=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin/iverilog.exe');VVP=IVERILOG.with_name('vvp.exe')
manifest=json.loads((MODEL/'manifest.json').read_text(encoding='utf8'))
crc=zlib.crc32(b''.join((MODEL/(name+'.hex')).read_bytes()for name in ['w1','b1','w2','b2'])+bytes([manifest['shift1']]))
manifest['model_crc32']=crc;(MODEL/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
params=','.join(f'.{k.upper()}_FILE("{(MODEL/(k+".hex")).as_posix()}")'for k in ['w1','b1','w2','b2'])+f',.SHIFT1({manifest["shift1"]})'
count=manifest['vector_count']
tb=f'''module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,load_valid=0,start=0;reg[4:0]load_address=0;reg[7:0]load_byte=0;
wire ready,busy,score_valid,result_valid;wire[3:0]score_index,result_class;wire signed[31:0]score;wire[31:0]margin;
reg[7:0]pixels[0:{count*32-1}];reg[31:0]expected[0:{count*11-1}];
integer v,i,cycles,seen,errors=0,best_idx;reg signed[31:0]best,second,current;reg[31:0]expected_margin;
omr_symbol_mlp #({params}) dut(.clk(clk),.rst_n(rst_n),.load_valid(load_valid),.load_address(load_address),.load_byte(load_byte),.start(start),.load_ready(ready),.busy(busy),.score_valid(score_valid),.score_index(score_index),.score(score),.result_valid(result_valid),.result_class(result_class),.result_margin(margin));
initial begin
 $readmemh("{(MODEL/'vectors_pixels.hex').as_posix()}",pixels);$readmemh("{(MODEL/'vectors_logits.hex').as_posix()}",expected);
 repeat(3)@(negedge clk);rst_n=1;
 // An interrupted calculation must produce no stale result after reset.
 start=1;@(negedge clk);start=0;repeat(200)@(negedge clk);rst_n=0;repeat(3)@(negedge clk);rst_n=1;
 for(v=0;v<{count};v=v+1)begin
  for(i=0;i<32;i=i+1)begin @(negedge clk);load_valid=1;load_address=i;load_byte=pixels[v*32+i];end
  @(negedge clk);load_valid=0;start=1;@(negedge clk);start=0;seen=0;cycles=0;
  while(!result_valid&&cycles<40000)begin
   @(negedge clk);cycles=cycles+1;
   // A busy request cannot replace the in-flight bitmap or restart inference.
   if(cycles==100)begin load_valid=1;load_address=0;load_byte=~pixels[v*32];start=1;end
   if(cycles==101)begin load_valid=0;start=0;end
   if(score_valid)begin
    if(score_index!==seen||score!==expected[v*11+seen])begin $display("LOGIT_FAIL vector=%0d class=%0d actual=%0d expected=%0d",v,seen,score,$signed(expected[v*11+seen]));$fatal;end
    seen=seen+1;
   end
  end
  best=32'sh80000000;second=32'sh80000000;best_idx=0;
  for(i=0;i<11;i=i+1)begin current=expected[v*11+i];if(current>best)begin second=best;best=current;best_idx=i;end else if(current>second)second=current;end
  expected_margin=$unsigned(best)-$unsigned(second);
  if(!result_valid||seen!=11||result_class!=best_idx||margin!==expected_margin||busy)begin $display("RESULT_FAIL vector=%0d seen=%0d",v,seen);$fatal;end
  @(negedge clk);
 end
 $display("PASS %0d vectors, %0d exact logits, cycles_per_glyph=%0d",{count},{count*11},cycles);$finish;
end
endmodule'''
(SIM/'tb_model.v').write_text(tb,encoding='ascii')
def run(name,sources):
    binary=SIM/(name+'.vvp')
    p=subprocess.run([str(IVERILOG),'-g2012','-s','tb','-o',str(binary),*map(str,sources)],capture_output=True,text=True,cwd=ROOT)
    (SIM/(name+'_compile.log')).write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0,p.stderr[-1800:]
    p=subprocess.run([str(VVP),str(binary)],capture_output=True,text=True,cwd=ROOT)
    (SIM/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0 and 'PASS' in p.stdout,p.stdout[-1800:]+p.stderr[-500:]
    print(p.stdout.strip(),flush=True)
run('model',[ROOT/'rtl/omr_symbol_mlp.v',SIM/'tb_model.v'])

with np.load(MODEL/'validation_vectors.npz')as vectors:
    bits=vectors['x'][0];scores=vectors['logits'][0];digit,margin=classify(scores)
raw=np.packbits(bits,bitorder='little').tobytes();identifier=(123).to_bytes(2,'little')
commands=[(0x60,identifier,0),(0x62,identifier,6),(0x61,identifier+b'\x02'+raw[:11],3),
          (0x60,identifier,0),(0x61,identifier+b'\x00'+raw[:11],0),(0x61,identifier+b'\x0b'+raw[11:22],0),
          (0x61,identifier+b'\x16'+raw[22:],0),(0x62,identifier,1),(0x63,identifier,0)]
packets=[frame(kind,i+1,data)for i,(kind,data,_)in enumerate(commands)]
flat=b''.join(packets);(SIM/'requests.hex').write_text(''.join(f'{b:02x}\n'for b in flat),encoding='ascii')
starts=[];n=0
for packet in packets:starts.append((n,len(packet)));n+=len(packet)
steps='\n'.join(f'send_request({start},{length},{i+1},{commands[i][2]});'for i,(start,length)in enumerate(starts))
tb=f'''module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,rx_valid=0,tx_ready=0;reg[7:0]rx_byte=0;wire tx_valid;wire[7:0]tx_byte;
reg[7:0]request[0:{len(flat)-1}],reply[0:19];integer received=0,ticks=0;
omr_serial_endpoint #({params},.MODEL_CRC(32'h{crc:08x})) dut(.clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),.tx_valid(tx_valid),.tx_byte(tx_byte),.tx_ready(tx_ready));
function[7:0]crc_next;input[7:0]prior,data;integer i;reg[7:0]c;begin c=prior^data;for(i=0;i<8;i=i+1)c=c[7]?(c<<1)^8'h07:c<<1;crc_next=c;end endfunction
always@(posedge clk)begin ticks<=ticks+1;if(tx_valid&&tx_ready)begin reply[received]=tx_byte;received=received+1;end end
always@(negedge clk)tx_ready=(ticks%3)!=0;
task send_request;input integer at,length,seq,status;integer j,timeout;reg[7:0]check;begin
 received=0;
 for(j=0;j<length;j=j+1)begin @(negedge clk);rx_valid=1;rx_byte=request[at+j];end
 @(negedge clk);rx_valid=0;timeout=0;while(received<20&&timeout<40000)begin @(negedge clk);timeout=timeout+1;end
 check=0;for(j=1;j<19;j=j+1)check=crc_next(check,reply[j]);
 if(received!=20||reply[0]!=165||reply[2]!=224||reply[3]!=seq||reply[4]!=14||reply[7]!=status||reply[19]!=check)begin $display("PROTOCOL_FAIL seq=%0d received=%0d status=%0d",seq,received,reply[7]);$fatal;end
 if(status==1&&(reply[8]!={int(digit)}||{{reply[12],reply[11],reply[10],reply[9]}}!=32'd{int(margin)}))$fatal(1,"Wrong inference payload");
 repeat(3)@(negedge clk);
end endtask
initial begin $readmemh("{(SIM/'requests.hex').as_posix()}",request);repeat(3)@(negedge clk);rst_n=1;
 // Damaged CRC cannot create an inference or ACK.
 for(integer j=0;j<8;j=j+1)begin @(negedge clk);rx_valid=1;rx_byte=j==7?request[j]^8'h01:request[j];end
 @(negedge clk);rx_valid=0;repeat(30)@(negedge clk);if(received!=0)$fatal(1,"Bad CRC was accepted");
 {steps}
 $display("PASS byte framing, CRC, missing data, wrong offset, valid inference, abort, TX stalls");$finish;end
endmodule'''
(SIM/'tb_protocol.v').write_text(tb,encoding='ascii')
run('protocol',[ROOT/'rtl/omr_symbol_mlp.v',ROOT/'rtl/omr_frame_endpoint.v',ROOT/'rtl/omr_serial_endpoint.v',ROOT/'rtl/ble_frame_parser.v',SIM/'tb_protocol.v'])
(OUT/'verification.json').write_text(json.dumps({'model_crc32':crc,'vectors':count,'logits_compared':count*11,'model_bit_exact':True,'protocol_rtl_passed':True,'physical_board_verified':False},indent=2),encoding='utf8')
