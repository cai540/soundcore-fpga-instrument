from pathlib import Path
import subprocess,os
R=Path(__file__).resolve().parents[1];B=R/'build/acceptance_20261102';BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin');os.environ['PATH']=str(BIN)+os.pathsep+os.environ['PATH']
s=(R/'tb/tb_natural_allocator.v').read_text().replace('tb_natural_allocator','tb_tools_custom_mapping')
s=s.replace('reg [3:0] key=0;','reg[48:0]custom_map;reg custom_map_enabled=0;reg [3:0] key=0;')
s=s.replace('.BANKED_MODE(1)', '.CUSTOM_MAP_AVAILABLE(1),.BANKED_MODE(1)').replace('.gate(gate),','.custom_map_enabled(custom_map_enabled),.custom_map(custom_map),.gate(gate),')
s=s.replace(' repeat(3)@(negedge clk);',' for(i=0;i<7;i=i+1)custom_map[i*7+:7]=i*10;\n repeat(3)@(negedge clk);')
s=s.replace(' if(!gate[5])', ''' remote_absolute=0;guide_override=0;custom_map_enabled=1;
 strike(0,0,0);strike(1,10,1);strike(6,60,0);
 guide_override=1;guide_pad=6;guide_note=71;strike(6,71,0);strike(6,71,1);
 remote_absolute=1;remote_note=7;strike(6,7,1);
 custom_map_enabled=0;guide_override=0;strike(6,64,0);
 if(!gate[5])''')
tb=B/'tb_tools_custom_mapping.v';tb.write_text(s);binary=B/'tb_tools_custom_mapping.vvp'
r=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s','tb_tools_custom_mapping','-o',str(binary),str(tb),str(R/'rtl/strike_voice_allocator32.v'),str(R/'rtl/pitch_layout.v')],cwd=R,capture_output=True,text=True);assert r.returncode==0,r.stderr
r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True);(B/'custom_mapping.log').write_text(r.stdout+r.stderr);print(r.stdout);assert r.returncode==0 and 'PASS'in r.stdout
