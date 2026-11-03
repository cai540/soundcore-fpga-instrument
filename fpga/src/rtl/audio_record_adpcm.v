// Capture of the actual FINAL audio output. Never connected to the FPGA sound source.
// 48 kHz ->127-tap anti-alias FIR ->8 kHz ->IMA ADPCM,8 seconds/32 KiB.
module audio_record_adpcm #(
 parameter integer MAX_SAMPLES=64000,
 parameter COEFF_FILE="@FPGA_ROOT@/src/assets/657e6a4e_tools_decimator.mem",
 parameter STEP_FILE="@FPGA_ROOT@/src/assets/9ddb1ea0_tools_ima_step.mem"
)(input wire clk,rst_n,input wire sample_tick,input wire signed[15:0] sample_in,
 input wire start,stop,input wire[15:0] start_token,
 output reg recording,output reg ready,output reg[16:0] sample_count,
 output reg[15:0] token,output reg[15:0] crc16,
 input wire[14:0] read_address,output reg[7:0] read_data);
 reg signed[15:0] coeff[0:126];reg[15:0] steps[0:127];
 initial begin $readmemh(COEFF_FILE,coeff);$readmemh(STEP_FILE,steps);end
 reg signed[15:0] history[0:127];reg[7:0] memory[0:32767];
 reg[6:0] write_ptr,tap;reg[2:0] decimate;reg filter_busy;
 reg signed[15:0] data_q,coeff_q;reg signed[47:0] acc;
 reg[1:0] fir_state;reg filtered_valid;reg signed[15:0] filtered;
 reg signed[15:0] predictor;reg[6:0] step_index;reg[3:0] low_nibble;
 reg finish_pending;
 integer i;integer diff,distance,delta,next_predictor,next_index;reg[3:0] code;
 wire[15:0] step=steps[step_index];
 wire signed[31:0] multiply=$signed(data_q)*$signed(coeff_q);
 wire signed[47:0] sum=acc+{{16{multiply[31]}},multiply};
 wire signed[47:0] scaled=sum>>>15;
 function[15:0] crc_byte;
 input[15:0] prior;input[7:0] value;reg[15:0] c;integer k;
 begin c=prior^{value,8'd0};for(k=0;k<8;k=k+1)c=c[15]?(c<<1)^16'h1021:c<<1;crc_byte=c;end endfunction
 always @* begin
  diff=$signed(filtered)-$signed(predictor);code=diff<0?4'd8:4'd0;distance=diff<0?-diff:diff;delta=step>>3;
  if(distance>=step)begin code=code|4;distance=distance-step;delta=delta+step;end
  if(distance>=(step>>1))begin code=code|2;distance=distance-(step>>1);delta=delta+(step>>1);end
  if(distance>=(step>>2))begin code=code|1;delta=delta+(step>>2);end
  next_predictor=$signed(predictor)+(code[3]?-delta:delta);
  if(next_predictor>32767)next_predictor=32767;if(next_predictor< -32768)next_predictor=-32768;
  case(code[2:0])0,1,2,3:next_index=step_index-1;4:next_index=step_index+2;5:next_index=step_index+4;6:next_index=step_index+6;default:next_index=step_index+8;endcase
  if(next_index<0)next_index=0;if(next_index>88)next_index=88;
 end
 // Registered read port; caller waits two clocks before packing a response.
 always @(posedge clk)read_data<=memory[read_address];
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   recording<=0;ready<=0;sample_count<=0;token<=0;crc16<=16'hffff;
   write_ptr<=0;tap<=0;decimate<=0;filter_busy<=0;fir_state<=0;acc<=0;
   data_q<=0;coeff_q<=0;filtered<=0;filtered_valid<=0;predictor<=0;step_index<=0;low_nibble<=0;finish_pending<=0;
  end else begin
   filtered_valid<=0;
   if(sample_tick)begin history[write_ptr]<=sample_in;write_ptr<=write_ptr+1'b1;end
   if(start && !recording && !(ready && token==start_token))begin
    recording<=1;ready<=0;sample_count<=0;token<=start_token;crc16<=16'hffff;
    decimate<=0;filter_busy<=0;fir_state<=0;predictor<=0;step_index<=0;low_nibble<=0;finish_pending<=0;
   end else if(recording)begin
    if(stop)begin recording<=0;filter_busy<=0;finish_pending<=1;end
    else begin
     if(sample_tick)begin
      if(decimate==5)begin decimate<=0;tap<=0;acc<=0;filter_busy<=1;fir_state<=0;end else decimate<=decimate+1'b1;
     end
     if(filter_busy)case(fir_state)
      0:begin data_q<=history[(write_ptr-7'd1-tap)&7'h7f];coeff_q<=coeff[tap];fir_state<=1;end
      1:begin
       acc<=sum;
       if(tap==126)begin filtered<=scaled>32767?16'sh7fff:scaled< -32768?16'sh8000:scaled[15:0];filtered_valid<=1;filter_busy<=0;end
       else begin tap<=tap+1'b1;fir_state<=0;end
      end
     endcase
     if(filtered_valid)begin
      predictor<=next_predictor;step_index<=next_index;sample_count<=sample_count+1'b1;
      if(!sample_count[0])low_nibble<=code;
      else begin memory[sample_count[15:1]]<={code,low_nibble};crc16<=crc_byte(crc16,{code,low_nibble});end
      if(sample_count==MAX_SAMPLES-1)begin recording<=0;finish_pending<=1;end
     end
    end
   end
   if(finish_pending)begin
    if(sample_count[0])begin memory[sample_count[15:1]]<={4'd0,low_nibble};crc16<=crc_byte(crc16,{4'd0,low_nibble});end
    ready<=1;finish_pending<=0;
   end
  end
 end
 // Power-up history must not leak undefined audio into a recording.
 initial for(i=0;i<128;i=i+1)history[i]=0;
endmodule
