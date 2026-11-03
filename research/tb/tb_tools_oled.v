`timescale 1ns/1ps
module tb_tools_oled;
 reg clk=0,rst_n=0,valid=1;always #1 clk=~clk;
 reg[1:0]mode=2;reg[511:0]wave={32{16'h2f00}};reg[255:0]bands;
 reg[7:0]header[0:767],expected;tri1 scl,sda;wire ready,nack;
 integer frame,count,p,col,b,y,h,i,fd;
 oled_status_ssd1315 #(.PRODUCT_TOOLS(1),.I2C_DIV(2),.REFRESH_CYCLES(2000)) dut(
  .clk(clk),.rst_n(rst_n),.bank(3'd2),.key(4'd0),.timbre(2'd1),.volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),
  .guide_step(11'd0),.guide_target(3'd7),.guide_target_bank(3'd0),.playback_state(2'd0),.auth_pending(1'b0),.remote_write_allowed(1'b1),.ble_frame_seen(1'b0),
  .pad_active(7'd0),.force_levels(56'd0),.contrast(8'h7f),.lyric_mode(1'b0),.lyric_phrase(7'd0),.lyric_character(5'd0),.lyric_progress(8'd0),.capture_payload(88'd0),
  .analysis_mode(mode),.analysis_valid(valid),.analysis_wave(wave),.analysis_spectrum(bands),.analysis_phase_bank(1'b0),.analysis_phase_pixels(8'h5a),
  .oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
 assign sda=(dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9)?1'b0:1'bz;
 initial begin
  $readmemh("rtl/tools_display_headers.mem",header);for(i=0;i<32;i=i+1)bands[i*8+:8]=i+1;
  repeat(3)@(negedge clk);rst_n=1;
  fd=$fopen("build/acceptance_20261102/oled_analysis_frames.hex","w");
  for(frame=0;frame<4;frame=frame+1)begin
   wait(dut.tx_start && dut.phase==2 && dut.page_index==0 && dut.column==0);@(negedge clk);count=0;
   while(count<1024)begin
    if(dut.tx_start && dut.phase==2)begin
     p=count/128;col=count%128;expected=0;
     if(p<2)expected=header[(frame==0?256:frame==3?512:0)+p*128+col];
     else if(frame==3)expected=8'h5a;
     else if(frame>0)expected=8'hff;
     else for(b=0;b<8;b=b+1)begin y=(p-2)*8+b;h=col/4+1;if(col%4!=3 && y>=48-h)expected[b]=1;end
     if(dut.tx_payload!==expected)$fatal(1,"analysis I2C frame=%0d byte=%0d got=%h expected=%h",frame,count,dut.tx_payload,expected);
     $fdisplay(fd,"%02x",dut.tx_payload);
     if(frame==0 && count==200)begin bands=0;mode=1;end
     if(frame==1 && count==200)begin valid=0;wave=0;end
     count=count+1;
    end
    @(negedge clk);
   end
   wait(dut.phase==3);@(negedge clk);
   if(frame==2)begin mode=3;valid=1;end
  end
  $fclose(fd);if(nack)$fatal(1,"unexpected NACK");
  $display("PASS:4096 actual I2C analysis bytes,Chinese header pipeline,FFT bars,waveform,phase,mid-frame mode change and valid-snapshot holding");$finish;
 end
 initial begin #10000000;$fatal(1,"analysis OLED timeout");end
endmodule
