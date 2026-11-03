`define TOOLS_GOWIN_RAM
// True1024-point fixed-point radix-2 FFT, waveform envelope and delayed phase plot.
// All analysis is a tap of final PCM; it never stalls or feeds back into synthesis.
// FFT uses rectangular windows and1/2 scaling at each stage (total1/1024).
module product_audio_analyzer #(
 parameter TWIDDLE_FILE="@FPGA_ROOT@/src/assets/f6697847_tools_fft_twiddle.mem",
 parameter EDGE_FILE="@FPGA_ROOT@/src/assets/d2e5103f_tools_fft_edges.mem"
)(input wire clk,rst_n,input wire sample_tick,input wire signed[15:0] sample_in,
 input wire frame_latch,output wire pending_frame,output reg[15:0] frame_id,
 output wire[511:0] wave_data,output wire[255:0] spectrum_data,
 output wire[511:0] phase_data,output wire phase_bank,
 input wire display_phase_bank,input wire[9:0] phase_address,output reg[7:0] phase_pixels);
 localparam CAP=0,ADDR=1,READ=2,MULT=3,BUTTER=4,WRITE=5,NEXT=6,
  PADDR=7,PREAD=8,POWER=9,NORMALIZE=10,CLEAR=11,DOTADDR=12,DOTWAIT=13,DOTWRITE=14,PENDING=15;
 reg[3:0] state;reg[9:0] captured,base,j,half;reg[3:0] stage;
`ifndef TOOLS_GOWIN_RAM
 reg signed[17:0] real_mem[0:1023],imag_mem[0:1023];
`endif
 reg[31:0] twiddle[0:511];reg[15:0] edges[0:32];
 initial begin $readmemh(TWIDDLE_FILE,twiddle);$readmemh(EDGE_FILE,edges);end
 function[9:0] reversed;input[9:0] v;integer b;begin for(b=0;b<10;b=b+1)reversed[b]=v[9-b];end endfunction
 reg[8:0] power_bin;reg[5:0] band;reg[18:0] maximum;
 wire[9:0] address_a=state==CAP ? reversed(captured) : state>=PADDR ? {1'b0,power_bin}:base+j;
 wire[9:0] address_b=base+j+half;
 wire signed[17:0] ra,rb,ia,ib;reg signed[15:0] wr,wi;
 wire[8:0] twiddle_address=j<<(9-stage);
 reg signed[17:0] a_real,a_imag;
 reg signed[34:0] product_r,product_i;
 reg signed[17:0] out_ar,out_ai,out_br,out_bi;
 wire signed[19:0] tr=product_r>>>15,ti=product_i>>>15;
 wire signed[20:0] ar_sum=$signed(a_real)+tr,ai_sum=$signed(a_imag)+ti;
 wire signed[20:0] br_sum=$signed(a_real)-tr,bi_sum=$signed(a_imag)-ti;
 // Arora V requires normal/write-through dual-port mode. Explicit primitives
 // avoid the synthesis tool selecting unsupported read-before-write mode.
 wire fft_wa=state==WRITE || (state==CAP && sample_tick);
 wire[17:0] fft_dra=state==WRITE ? out_ar:{{2{sample_in[15]}},sample_in};
 wire[17:0] fft_dia=state==WRITE ? out_ai:18'd0;
`ifdef TOOLS_GOWIN_RAM
 DPX9B #(.BIT_WIDTH_0(18),.BIT_WIDTH_1(18),.READ_MODE0(0),.READ_MODE1(0),.WRITE_MODE0(2'b01),.WRITE_MODE1(2'b01)) real_ram(
  .CLKA(clk),.CLKB(clk),.CEA(1'b1),.CEB(1'b1),.OCEA(1'b1),.OCEB(1'b1),.RESETA(1'b0),.RESETB(1'b0),.BLKSELA(3'd0),.BLKSELB(3'd0),
  .ADA({address_a,4'b0011}),.ADB({address_b,4'b0011}),.WREA(fft_wa),.WREB(state==WRITE),.DIA(fft_dra),.DIB(out_br),.DOA(ra),.DOB(rb));
 DPX9B #(.BIT_WIDTH_0(18),.BIT_WIDTH_1(18),.READ_MODE0(0),.READ_MODE1(0),.WRITE_MODE0(2'b01),.WRITE_MODE1(2'b01)) imag_ram(
  .CLKA(clk),.CLKB(clk),.CEA(1'b1),.CEB(1'b1),.OCEA(1'b1),.OCEB(1'b1),.RESETA(1'b0),.RESETB(1'b0),.BLKSELA(3'd0),.BLKSELB(3'd0),
  .ADA({address_a,4'b0011}),.ADB({address_b,4'b0011}),.WREA(fft_wa),.WREB(state==WRITE),.DIA(fft_dia),.DIB(out_bi),.DOA(ia),.DOB(ib));
`else
 reg signed[17:0] ra_q,rb_q,ia_q,ib_q;
 assign ra=ra_q;assign rb=rb_q;assign ia=ia_q;assign ib=ib_q;
 always @(posedge clk)begin
  if(fft_wa)begin real_mem[address_a]<=fft_dra;imag_mem[address_a]<=fft_dia;ra_q<=fft_dra;ia_q<=fft_dia;end
  else begin ra_q<=real_mem[address_a];ia_q<=imag_mem[address_a];end
 end
 always @(posedge clk)begin
  if(state==WRITE)begin real_mem[address_b]<=out_br;imag_mem[address_b]<=out_bi;rb_q<=out_br;ib_q<=out_bi;end
  else begin rb_q<=real_mem[address_b];ib_q<=imag_mem[address_b];end
 end
`endif
 always @(posedge clk){wi,wr}<=twiddle[twiddle_address];
 reg signed[15:0] wave_min[0:31],wave_max[0:31];
 reg signed[15:0] phase_x[0:31],phase_y[0:31],phase_delay[0:63];
 reg[5:0] delay_pointer;reg signed[15:0] current_min,current_max;reg[15:0] peak;
 wire[15:0] absolute_sample=sample_in[15] ? -sample_in:sample_in;
 wire signed[15:0] next_min=sample_in<current_min ? sample_in:current_min;
 wire signed[15:0] next_max=sample_in>current_max ? sample_in:current_max;
 reg[511:0] wave_back;reg[255:0] spectrum_back;
 reg[511:0] phase_back;reg pending,front_bank;
 assign pending_frame=pending;assign phase_bank=pending ? !front_bank:front_bank;
 // These vectors are coherent while pending_frame=1. Consumers latch once;
 // the OLED has its own refresh snapshot, so duplicating a front vector here
 // would waste 1792 registers. The bitmap remains double buffered in BSRAM.
 assign wave_data=wave_back;
 assign spectrum_data=spectrum_back;
 assign phase_data=phase_back;
 wire[18:0] magnitude=(ra<0?-ra:ra)+(ia<0?-ia:ia);
 wire[18:0] largest=magnitude>maximum ? magnitude:maximum;
 function[7:0] bar_height;input[18:0] x;integer b;reg[5:0] log_value;
 begin log_value=0;for(b=0;b<19;b=b+1)if(x[b])log_value=b;
 bar_height=x<4 ? 0:log_value>=16 ? 48:log_value*3;end endfunction
 reg[4:0] normalization_shift;reg[6:0] normalize_index;
 integer k,shift_value,mapped_lo,mapped_hi,mapped_x,mapped_y;
 always @* begin
  shift_value=0;for(k=0;k<16;k=k+1)if(peak[k] && k>4)shift_value=k-4;
  mapped_lo=24-($signed(wave_min[normalize_index[4:0]])>>>normalization_shift);
  mapped_hi=24-($signed(wave_max[normalize_index[4:0]])>>>normalization_shift);
  mapped_x=64+2*($signed(phase_x[normalize_index[4:0]])>>>normalization_shift);
  mapped_y=24-($signed(phase_y[normalize_index[4:0]])>>>normalization_shift);
  if(mapped_lo<0)mapped_lo=0;if(mapped_lo>47)mapped_lo=47;
  if(mapped_hi<0)mapped_hi=0;if(mapped_hi>47)mapped_hi=47;
  if(mapped_x<0)mapped_x=0;if(mapped_x>127)mapped_x=127;
  if(mapped_y<0)mapped_y=0;if(mapped_y>47)mapped_y=47;
 end
 reg[9:0] clear_index,plot_address;
 reg[5:0] dot_index;reg[2:0] plot_bit;wire[7:0] plot_old;
 wire[6:0] dot_x=phase_back[dot_index*16 +: 7];
 wire[5:0] dot_y=phase_back[dot_index*16+8 +: 6];
 wire[9:0] render_address=state==CLEAR ? clear_index:plot_address;
 wire[7:0] bitmap_write=state==CLEAR ? 8'd0:plot_old|(8'b1<<plot_bit);
`ifdef TOOLS_GOWIN_RAM
 wire[15:0] bitmap_a,bitmap_b;
 DPB #(.BIT_WIDTH_0(8),.BIT_WIDTH_1(8),.READ_MODE0(0),.READ_MODE1(0),.WRITE_MODE0(2'b01),.WRITE_MODE1(2'b01)) bitmap_ram(
  .CLKA(clk),.CLKB(clk),.CEA(1'b1),.CEB(1'b1),.OCEA(1'b1),.OCEB(1'b1),.RESETA(1'b0),.RESETB(1'b0),.BLKSELA(3'd0),.BLKSELB(3'd0),
  .ADA({!front_bank,render_address,3'b000}),.ADB({display_phase_bank,phase_address,3'b000}),.WREA(state==CLEAR || state==DOTWRITE),.WREB(1'b0),
  .DIA({8'd0,bitmap_write}),.DIB(16'd0),.DOA(bitmap_a),.DOB(bitmap_b));
 assign plot_old=bitmap_a[7:0];always @* phase_pixels=bitmap_b[7:0];
`else
 reg[7:0] phase_bitmap[0:2047];reg[7:0] plot_old_q;
 assign plot_old=plot_old_q;
 always @(posedge clk)begin
  phase_pixels<=phase_bitmap[{display_phase_bank,phase_address}];
  if(state==CLEAR || state==DOTWRITE)begin phase_bitmap[{!front_bank,render_address}]<=bitmap_write;plot_old_q<=bitmap_write;end
  else plot_old_q<=phase_bitmap[{!front_bank,render_address}];
 end
`endif
 integer reset_i;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=CAP;captured<=0;base<=0;j<=0;half<=1;stage<=0;
   power_bin<=1;band<=0;maximum<=0;a_real<=0;a_imag<=0;product_r<=0;product_i<=0;
   out_ar<=0;out_ai<=0;out_br<=0;out_bi<=0;current_min<=32767;current_max<=-32768;peak<=0;
   delay_pointer<=0;wave_back<=0;spectrum_back<=0;
   phase_back<=0;pending<=0;front_bank<=0;frame_id<=0;
   normalize_index<=0;normalization_shift<=0;clear_index<=0;plot_address<=0;plot_bit<=0;dot_index<=0;
   for(reset_i=0;reset_i<64;reset_i=reset_i+1)phase_delay[reset_i]<=0;
  end else begin
   if(sample_tick)begin phase_delay[delay_pointer]<=sample_in;delay_pointer<=delay_pointer+1'b1;end
   case(state)
    CAP:if(sample_tick)begin
     current_min<=next_min;current_max<=next_max;
     if(absolute_sample>peak)peak<=absolute_sample;
     if(captured[4:0]==31)begin
      wave_min[captured[9:5]]<=next_min;wave_max[captured[9:5]]<=next_max;
      current_min<=32767;current_max<=-32768;
     end
     if(captured[4:0]==0)begin phase_x[captured[9:5]]<=sample_in;phase_y[captured[9:5]]<=phase_delay[delay_pointer];end
     if(captured==1023)begin state<=ADDR;base<=0;j<=0;half<=1;stage<=0;end
     else captured<=captured+1'b1;
    end
    ADDR:state<=READ;
    READ:state<=MULT;
    MULT:begin
     a_real<=ra;a_imag<=ia;
     product_r<=$signed(rb)*$signed(wr)-$signed(ib)*$signed(wi);
     product_i<=$signed(rb)*$signed(wi)+$signed(ib)*$signed(wr);state<=BUTTER;
    end
    BUTTER:begin out_ar<=ar_sum>>>1;out_ai<=ai_sum>>>1;out_br<=br_sum>>>1;out_bi<=bi_sum>>>1;state<=WRITE;end
    WRITE:state<=NEXT;
    NEXT:begin
     if(j+1<half)begin j<=j+1'b1;state<=ADDR;end
     else if(base+{half,1'b0}<1024)begin base<=base+{half,1'b0};j<=0;state<=ADDR;end
     else if(stage<9)begin stage<=stage+1'b1;half<=half<<1;base<=0;j<=0;state<=ADDR;end
     else begin power_bin<=1;band<=0;maximum<=0;state<=PADDR;end
    end
    PADDR:state<=PREAD;
    PREAD:state<=POWER;
    POWER:begin
     if(power_bin+1>=edges[band+1])begin
      spectrum_back[band*8 +: 8]<=bar_height(largest);maximum<=0;
      if(band==31)begin normalize_index<=0;normalization_shift<=shift_value;state<=NORMALIZE;end
      else begin band<=band+1'b1;power_bin<=power_bin+1'b1;state<=PADDR;end
     end else begin maximum<=largest;power_bin<=power_bin+1'b1;state<=PADDR;end
    end
    NORMALIZE:begin
     phase_back[normalize_index*16 +: 16]<={mapped_y[7:0],mapped_x[7:0]};
     if(normalize_index<32)wave_back[normalize_index*16 +: 16]<={mapped_lo[7:0],mapped_hi[7:0]};
     if(normalize_index==31)begin clear_index<=0;state<=CLEAR;end else normalize_index<=normalize_index+1'b1;
    end
    CLEAR:if(clear_index==767)begin dot_index<=0;state<=DOTADDR;end else clear_index<=clear_index+1'b1;
    DOTADDR:begin plot_address<={dot_y[5:3],dot_x};plot_bit<=dot_y[2:0];state<=DOTWAIT;end
    DOTWAIT:state<=DOTWRITE;
    DOTWRITE:if(dot_index==31)begin pending<=1;state<=PENDING;end else begin dot_index<=dot_index+1'b1;state<=DOTADDR;end
    PENDING:if(frame_latch)begin
     front_bank<=!front_bank;
     frame_id<=frame_id+1'b1;pending<=0;captured<=0;peak<=0;current_min<=32767;current_max<=-32768;state<=CAP;
    end
    default:state<=CAP;
   endcase
  end
 end
endmodule
