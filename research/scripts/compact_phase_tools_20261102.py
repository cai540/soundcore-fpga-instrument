from pathlib import Path
R=Path(__file__).resolve().parents[1]
def edit(name,pairs):
 p=R/name;s=p.read_text('utf8')
 for a,b in pairs:assert a in s,(name,a);s=s.replace(a,b)
 p.write_text(s,encoding='utf8')
edit('rtl/product_audio_analyzer.v',[
 ('output wire[1023:0] phase_data','output wire[511:0] phase_data'),
 ('reg signed[15:0] phase_x[0:63],phase_y[0:63],phase_delay[0:63];','reg signed[15:0] phase_x[0:31],phase_y[0:31],phase_delay[0:63];'),
 ('reg[1023:0] phase_back','reg[511:0] phase_back'),
 ('phase_x[normalize_index[5:0]]','phase_x[normalize_index[4:0]]'),('phase_y[normalize_index[5:0]]','phase_y[normalize_index[4:0]]'),
 ("if(captured[3:0]==0)begin phase_x[captured[9:4]]<=sample_in;phase_y[captured[9:4]]<=phase_delay[delay_pointer];end","if(captured[4:0]==0)begin phase_x[captured[9:5]]<=sample_in;phase_y[captured[9:5]]<=phase_delay[delay_pointer];end"),
 ('normalize_index==63','normalize_index==31'),('dot_index==63','dot_index==31'),
 ('.WRITE_MODE0(1),.WRITE_MODE1(1)',".WRITE_MODE0(2'b01),.WRITE_MODE1(2'b01)")])
edit('rtl/product_tools_engine.v',[
 ('input wire[255:0] spectrum_data,input wire[1023:0] phase_data','input wire[255:0] spectrum_data,input wire[511:0] phase_data'),
 ('reg[1023:0] frozen','reg[511:0] frozen'),
 ("frozen<=value==0 ? {512'd0,wave_data}:value==1?{768'd0,spectrum_data}:phase_data;","frozen<=value==0 ? wave_data:value==1?{256'd0,spectrum_data}:phase_data;"),
 ('frozen_length<=value==0?64:value==1?32:128;','frozen_length<=value==1?32:64;'),
 ("(value==0?8'd64:value==1?8'd32:8'd128)","(value==1?8'd32:8'd64)")])
edit('rtl/product_tools_subsystem.v',[('wire[1023:0] phase_data','wire[511:0] phase_data')])
edit('tb/tb_tools_analyzer.v',[('wire[1023:0]points','wire[511:0]points')])
edit('tb/tb_tools_protocol.v',[(".phase_data({128{8'h77}})",".phase_data({64{8'h77}})")])
edit('tb/tb_tools_bulk_endpoint.v',[(".phase_data(1024'd0)",".phase_data(512'd0)")])
A='app/android/app/src/main/java/cn/soundcore/instrument/'
edit(A+'ProductToolsController.kt',[('listOf(64,32,128)[kind]','listOf(64,32,64)[kind]')])
edit(A+'ProductToolsPanel.kt',[
 ('if(data.size==128){val path=Path();repeat(64)','if(data.size==64){val path=Path();repeat(32)'),
 ('实际发声','活动声部')])
print('32-point phase plot and512-bit shared snapshot; original1024 FFT/audio/recording unchanged')
