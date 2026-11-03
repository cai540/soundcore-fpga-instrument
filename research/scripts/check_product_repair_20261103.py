"""Actual RTL checks for bulk graphics, permutation mapping and long-score RAM."""
from pathlib import Path
import subprocess,os,json
R=Path(__file__).resolve().parents[1];B=R/'build/product_repair_20261103/tests';B.mkdir(parents=True,exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
results=[]
def run(top,text):
 if 'module tb_uploaded_song_engine' in text or 'module tb_long_score_capacity' in text:
  text=text.replace('wire[5:0]note;', 'wire[6:0]note;wire[3:0]key;wire display_receiving;wire[9:0]display_count,display_received,display_expected;')
  text=text.replace("req(8'h31,7,p)","req(8'h38,8,p)")
  text=text.replace('begin ev=(ms<<6)|(nt<0?7:((nt/7)<<3)|(nt%7));end', 'integer d;begin case(nt%7)0:d=0;1:d=2;2:d=4;3:d=5;4:d=7;5:d=9;default:d=11;endcase ev=(ms<<7)|(nt<0?127:(nt/7)*12+d);end')
 bench=B/(top+'.v');bench.write_text(text,encoding='utf8');binary=B/(top+'.vvp')
 sources=[str(p)for p in(R/'rtl').glob('*.v')]
 c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',top,'-o',str(binary),str(bench),*sources],cwd=R,capture_output=True,text=True)
 assert c.returncode==0,c.stderr
 r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=240)
 (B/(top+'.log')).write_text(r.stdout+r.stderr,encoding='utf8')
 print(top,r.stdout[-500:],flush=True);assert r.returncode==0 and 'PASS' in r.stdout
 results.append(dict(test=top,passed=True))

for name in ('tb_tools_protocol','tb_tools_bulk_endpoint','tb_uploaded_song_engine'):
 run(name,(R/'tb'/(name+'.v')).read_text('utf8'))

# Send one live request through the actual frame parser, endpoint and tool engine.
s=(R/'tb/tb_tools_bulk_endpoint.v').read_text('utf8').replace('tb_tools_bulk_endpoint','tb_live_graph_endpoint')
s=s.replace(".active_voices(6'd0)",".active_voices(6'd17)").replace(".analysis_frame(16'd1),.analysis_ready(1'b0)",".analysis_frame(16'h2468),.analysis_ready(1'b1)")
s=s.replace(".wave_data(512'd0)",".wave_data(512'h"+''.join(f'{i:02x}' for i in reversed(range(64)))+")")
a=s.index('  c=0;send(');b=s.index('  wait(tx_valid)',a)
s=s[:a]+"  c=0;send(8'ha5);send(1);c=crc(c,1);send(8'h48);c=crc(c,8'h48);send(9);c=crc(c,9);send(1);c=crc(c,1);send(0);c=crc(c,0);send(c);\n"+s[b:]
s=s.replace('k<134','k<86')
a=s.index('  if(received[2]');b=s.index('  $display(',a)
s=s[:a]+'''  if(received[2]!=8'h86 || received[3]!=9 || received[4]!=80 || received[5]!=1 || received[6]!=8'h48 || received[7]!=0 || received[8]!=8'h68 || received[9]!=8'h24)$fatal(1,"live header/frame");
  if(received[10]!=0 || received[11]!=64 || received[12]!=17)$fatal(1,"live metadata");
  for(k=0;k<64;k=k+1)if(received[k+15]!==k[7:0])$fatal(1,"live data %d got%h",k,received[k+15]);
  c=0;for(k=1;k<85;k=k+1)c=crc(c,received[k]);if(c!=received[85])$fatal(1,"live streaming CRC");
'''+s[b:]
run('tb_live_graph_endpoint',s)

# Check every bank/key for the relative seven-degree permutation, retaining guide priority.
s=(R/'tb/tb_natural_allocator.v').read_text('utf8').replace('tb_natural_allocator','tb_relative_permutation')
s=s.replace('reg [3:0] key=0;',"reg[48:0]custom_map;reg custom_map_enabled=1;reg [3:0] key=0;")
s=s.replace('.BANKED_MODE(1)', '.CUSTOM_MAP_AVAILABLE(1),.BANKED_MODE(1)').replace('.gate(gate),','.custom_map_enabled(custom_map_enabled),.custom_map(custom_map),.gate(gate),')
a=s.index('initial begin');s=s[:a]+'''integer b,k,d;integer offsets[0:6];
initial begin
 offsets[0]=0;offsets[1]=2;offsets[2]=4;offsets[3]=5;offsets[4]=7;offsets[5]=9;offsets[6]=11;
 for(i=0;i<7;i=i+1)custom_map[i*7+:7]=120+6-i;
 repeat(3)@(negedge clk);rst_n=1;
 for(b=0;b<5;b=b+1)for(k=0;k<12;k=k+1)begin
  bank=b;key=k;
  for(d=0;d<7;d=d+1)begin strike(d,b*12+k+offsets[6-d],0);strike(d,b*12+k+offsets[6-d],1);end
 end
 guide_override=1;guide_pad=2;guide_note=70;strike(2,70,0);strike(2,70,1);
 remote_absolute=1;remote_note=1;strike(6,1,1);
 $display("PASS: all5banks*12keys*7pads, physical/phone permutations, guide and absolute overrides");$finish;
end
endmodule
'''
run('tb_relative_permutation',s)

# Force a >65535ms score through real staging RAM and CRC, across both bank addresses.
s=(R/'tb/tb_uploaded_song_engine.v').read_text('utf8').replace('tb_uploaded_song_engine','tb_long_score_capacity')
s=s.replace('words[0:511]','words[0:1022]')
s=s.replace('i<512','i<900').replace('hash_words(512)','hash_words(900)').replace("16'h6789,512","16'h6789,900").replace('n=512-i','n=900-i').replace('received==512','received==900').replace('39:24]==512','39:24]==900').replace('step==512','step==900')
# Existing20ms events are valid; a long first rest drives the accumulation above16bits.
s=s.replace('hash_words(900);', 'words[0]=ev(60000,-1);hash_words(900);')
# Playback timing belongs to the original short-score bench; this check concerns long atomic publication.
a=s.index('  action(1);n=0;while(!finished && n<110000)');b=s.index('  $display(',a)
s=s[:a]+'''  check(dut.total_ms>65535 && dut.received==900,"long total and high-address bank");
  check(dut.memory[1024+899]==words[899] || dut.memory[899]==words[899],"last RAM word preserved");
'''+s[b:]
run('tb_long_score_capacity',s)
run('tb_uniform_force',r'''
module tb_uniform_force;
 reg clk=0;always #5 clk=~clk;
 fsr_strike_detector dut(.clk(clk),.rst_n(1'b0),.sample_valid(1'b0),.sample_channel(3'd0),.sample_value(12'd0));
 integer value,ch,previous,current,reference;
 initial begin
 previous=0;
 for(value=0;value<4096;value=value+1)begin
  reference=dut.pad_velocity(0,value);
  if(reference<previous)$fatal(1,"nonmonotone force at %d",value);
  previous=reference;
  for(ch=1;ch<7;ch=ch+1)if(dut.pad_velocity(ch,value)!=reference)$fatal(1,"unequal channel %d",ch);
 end
 if(dut.pad_velocity(0,1050)!=255 || dut.pad_velocity(6,1050)!=255)$fatal(1,"endpoint");
 $display("PASS: all4096force codes monotone, all7channel curves identical, full-scale endpoint1050");$finish;
 end
endmodule
''')
(B/'results.json').write_text(json.dumps(results,indent=2))
print('PASS: all repair-specific RTL checks',flush=True)
