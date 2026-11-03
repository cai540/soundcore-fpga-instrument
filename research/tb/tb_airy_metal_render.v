`timescale 1ns/1ps
module tb_airy_metal_render;
reg clk=0,rst_n=0,tick=0,hit=0;
always #1 clk=~clk;
reg[6:0]note=12;reg[7:0]velocity=210,bend=128;reg[3:0]drive=4;
wire signed[15:0]raw,metal;wire raw_valid,metal_valid,overflow,fx_overflow;
integer style=0,n,fd,elapsed;reg seen_raw,seen_metal;
reg[1023:0]destination;
handpan_modal32 source(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.enabled(1'b1),
 .strike_valid(hit),.strike_note(note),.strike_velocity(velocity),.rhythmic(style!=0),.bend(bend),
 .sample_out(raw),.sample_valid(raw_valid),.overflow(overflow),.active_count());
rock_voice_fx fx(.clk(clk),.rst_n(rst_n),.enabled(style!=0),.input_valid(raw_valid),
 .sample_in(raw),.drive(drive),.tone(bend),.sample_out(metal),.sample_valid(metal_valid),.overflow(fx_overflow));
always @(negedge clk)begin
 if(raw_valid)seen_raw=1;
 if(metal_valid)seen_metal=1;
end
initial begin
 if($value$plusargs("style=%d",style))begin end
 if(!$value$plusargs("out=%s",destination))$fatal(1,"missing output path");
 fd=$fopen(destination,"w");repeat(3)@(negedge clk);rst_n=1;
 for(n=0;n<384000;n=n+1)begin
  if(n%18000==0 && n<288000)begin
   case((n/18000)%8)
    0:note=12;1:note=19;2:note=21;3:note=24;4:note=12;5:note=26;6:note=21;7:note=19;
   endcase
   velocity=190;@(negedge clk);hit=1;@(negedge clk);hit=0;
  end
  if(n>=288000 && n<312000 && n%4000==0)begin
   note=24;velocity=170;@(negedge clk);hit=1;@(negedge clk);hit=0;
  end
  // Second half demonstrates the actual drive and slider inputs, not an audio effect added later.
  if(style!=0 && n>=192000)begin
   drive=(n-192000)/12000;
   bend=((n-192000)%96000)*255/96000;
  end
  seen_raw=0;seen_metal=0;
  @(negedge clk);tick=1;@(negedge clk);tick=0;
  repeat(254)@(negedge clk);
  if(!seen_raw || (style!=0 && !seen_metal) || overflow || fx_overflow)$fatal(1,"render missed 256-clock audio frame");
  $fwrite(fd,"%d\n",style==0 ? raw:metal);
 end
 $fclose(fd);$display("PASS: actual RTL render style=%d samples=384000 deadline=256",style);$finish;
end
endmodule
