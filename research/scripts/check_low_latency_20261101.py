from pathlib import Path
import os,subprocess,json,re,argparse,xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[1];O=R/'build/low_latency_20261101/tests';O.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+');args=parser.parse_args()
os.environ.update(TEMP=str(R/'tmp'),TMP=str(R/'tmp'));(R/'tmp').mkdir(exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
results=json.loads((O/'results.json').read_text())if args.only and (O/'results.json').exists()else []
def run(name,source,sources):
    if args.only and name not in args.only:return
    # Icarus on Windows crashes while zero-padding a 1-bit constant at the
    # widened two-bit status enum. Give the exact new port width in fixtures.
    source=source.replace(".timbre(1'b1)",".timbre(2'd1)").replace(".timbre(1'b0)",".timbre(2'd0)")
    tb=O/(name+'.v');tb.write_text(source,encoding='utf8');binary=O/(name+'.vvp')
    c=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',name,'-o',str(binary),str(tb),*map(str,sources)],cwd=R,capture_output=True,text=True)
    assert c.returncode==0,(name,c.returncode,c.stdout,c.stderr)
    r=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=120)
    body=r.stdout+r.stderr;(O/(name+'.log')).write_text(body)
    passed=r.returncode==0 and 'PASS' in body and 'FATAL'not in body
    results[:]=[row for row in results if row['test']!=name]+[dict(test=name,passed=passed,output=body)]
    (O/'results.json').write_text(json.dumps(results,indent=2))
    print(name,body[-700:],flush=True);assert passed,name
rtl=list((R/'rtl').glob('*.v'))
for name in ['tb_low_latency_attack','tb_compact_remote_release','tb_natural_pitch_contract','tb_natural_allocator','tb_natural_ble','tb_absolute_remote_bridge','tb_k5_lamp_follow','tb_remote_note_bridge','tb_ble_realtime_endpoint',
    'tb_oled_i2c_write2','tb_oled_reconnect','tb_oled_dual_address','tb_oled_event_refresh','tb_oled_force_geometry','tb_oled_karaoke_integration']:
    text=(R/'tb'/(name+'.v')).read_text(encoding='utf8')
    if(name=='tb_ble_realtime_endpoint'):
        text=text.replace('wire [55:0] payload','wire [111:0] payload').replace(".bank(3'd0)",".key(4'd0),.bank(3'd0)")
    if name.startswith('tb_oled'):
        text=re.sub(r'(oled_status_ssd1315.*?)(\.bank\()',lambda m:m[1]+".key(4'd0),"+m[2],text,count=1,flags=re.S)
    run(name,text,rtl)
# Existing transaction test is retained with expected output positions migrated;
# the original V1 bytes, CRC, rollback, 512-event and retry assertions stay intact.
text=(R/'tb/tb_uploaded_song_engine.v').read_text().replace('wire[5:0]note','wire[3:0]key;wire[6:0]note')
text=text.replace('dut(.*);','dut(.display_receiving(),.display_count(),.display_received(),.display_expected(),.*);')
text=text.replace('note==0','note==24').replace('bank==4 && pad==6','bank==4 && pad==5').replace('strike_pad=6;','strike_pad=5;')
run('tb_uploaded_song_engine',text,rtl)
# 128 pitch codes x 256 bends, all 32 voice contexts, atomic frame controls.
oracle=[]
for bend in range(256):
    for note in range(128):
        step=round(440*2**((36+note-69)/12)*2**32/48000) if note<72 else 0
        oracle.append(f'{step*(65536+(bend-128)*30)>>16:08x}')
(O/'pitch_oracle.mem').write_text('\n'.join(oracle)+'\n')
text=(R/'tb/tb_shared_pitch_snapshot.v').read_text().replace('[191:0]','[223:0]').replace('[0:16383]','[0:32767]')
text=text.replace('group_i<2','group_i<4').replace('*6+:6','*7+:7').replace('note_i<35','note_i<72').replace('bend_i*64+note_i','bend_i*128+note_i')
text=text.replace('age>200','age>240').replace('repeat(219)','repeat(239)').replace('repeat(36)','repeat(16)').replace('#2000000','#4000000')
text=text.replace('build/shared_pitch_20261028/pitch_oracle.mem',(O/'pitch_oracle.mem').as_posix())
text=text.replace('playable_synth32 dut','playable_synth32 #(.EXPRESSION_TEXTURE(2)) dut').replace('.velocity(velocity),.bend(bend)',".velocity(velocity),.expression({32{8'd176}}),.bend(bend)")
run('tb_shared_pitch_snapshot',text,rtl)
text=(R/'tb/tb_uploaded_song_engine.v').read_text().replace('tb_uploaded_song_engine','tb_absolute_song_engine')
text=text.replace('wire[5:0]note','wire[3:0]key;wire[6:0]note').replace('dut(.*);','dut(.display_receiving(),.display_count(),.display_received(),.display_expected(),.*);')
text=text.replace('(ms<<6)|(nt<0?7:((nt/7)<<3)|(nt%7))','(ms<<7)|(nt<0?127:nt)')
text=text.replace("req(8'h31,7,p)","req(8'h38,8,p)").replace('ev(300,34)','ev(300,71)')
text=text.replace('words[0]=(20<<6)|(5<<3)','words[0]=(20<<7)|72')
run('tb_absolute_song_engine',text,rtl)
text=(R/'tb/tb_product_song_guide.v').read_text().replace('.song_select(song)',".key(song ? 4'd2:4'd5),.song_select(song)")
run('tb_product_song_guide',text,rtl)
text=(R/'tb/tb_native_panel_transport.v').read_text().replace('wire [5:0] note','wire [6:0] note')
text=text.replace(".remote_payload(56'd0),.player_finished(finished),",".remote_payload(56'd0),.guide_finished(1'b0),.player_finished(finished),")
text=text.replace('.song_select(song[0]),',".key(4'd0),.song_select(song[0]),").replace('if(bank!=1)','if(bank!=3)').replace('if(bank!=0)','if(bank!=2)')
text=text.replace('note!=8','note!=32')
text=text.replace('wire vibrato,timbre,','wire [1:0] timbre;wire vibrato,')
run('tb_native_panel_transport',text,rtl)
# Actual Kotlin-encoded layout2 transaction, not a second Python encoder.
text=(R/'tb/tb_melody_upload_endpoint.v').read_text().replace('wire[5:0]note','wire[6:0]note')
text=text.replace('build/mono_recognition_20261028/fixtures/','build/vocal_app_20261028/fixtures/')
text=text.replace(".bank(3'd0)",".key(4'd0),.bank(3'd0)")
text=text.replace('response[7]!=0','response[7]!=0 || response[5]!=2')
run('tb_melody_upload_endpoint',text,rtl)
text=(R/'build/fpga_omr_20261031/simulation/tb_integrated.v').read_text(encoding='utf8')
text=text.replace('module tb;','module tb_integrated_omr;').replace(".bank('0)",".key(4'd0),.bank('0)")
run('tb_integrated_omr',text,rtl)
text=(R/'tb/tb_expression_core.v').read_text().replace('module tb_expression_core','module tb_natural_speaker_core')
start=text.index('    always @(posedge dut.sample_tick)');end=text.index('    pressure_i2s_additive32_core',start)
receiver='''    always @(posedge dut.sample_tick)if(rst_n)begin ready=1;bits=0;end
    always @(posedge bck)if(rst_n && ready)begin
        if(ws!==(bits>=32))$fatal(1,"speaker I2S WS mismatch");
        if(bits==1)begin expected=dut.output_sample;decoded=0;end
        if(bits==33)decoded=0;
        if((bits>=1&&bits<=16)||(bits>=33&&bits<=48))begin
            decoded={decoded[14:0],din};
            if(bits==16||bits==48)begin
                if(decoded!==expected)$fatal(1,"speaker I2S sample mismatch");words=words+1;
            end
        end else if(din!==0)$fatal(1,"I2S padding bit was not zero");
        bits=bits+1;
    end
'''
text=(text[:start]+receiver+text[end:]).replace('.HEADPHONE_OUTPUT(1)','.HEADPHONE_OUTPUT(0)')
text=text.replace(".panel_bank(3'd0)",".panel_key(4'd0),.guide_override(1'b0),.guide_pad(3'd0),.guide_note(7'd0),.remote_absolute(1'b0),.remote_note(7'd0),.panel_bank(3'd0)")
text=text.replace(".panel_timbre(1'b1)",".panel_timbre(1'b1),.panel_handpan_style(2'd0)")
text=text.replace('if(owner<0 || events!=1)',"if(owner<0 || events!=1 || dut.note_index[owner*7+:7]!=2)")
run('tb_natural_speaker_core',text,rtl+[R/'board/pressure_i2s_additive32_core.v'])
print('Natural layout regression passed:',len(results))
