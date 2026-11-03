`timescale 1ns/1ps
module tb_capture_oled_i2c;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0;reg [87:0]payload=0;
 tri1 scl,sda;wire ready,nack;wire [7:0]reference;
 integer frames=0,bytes_seen=0,checks=0;reg [7:0]last_stage=0;
 oled_status_ssd1315 #(.CAPTURE_OVERLAY(1),.I2C_DIV(1),.REFRESH_CYCLES(10000000)) dut(
  .clk(clk),.rst_n(rst_n),.bank(3'd2),.timbre(1'b1),.volume(5'd16),.vibrato(1'b0),
  .ui_state(2'd0),.guide_step(11'd12),.guide_target(3'd4),.guide_target_bank(3'd2),.playback_state(2'd0),
  .auth_pending(1'b0),.remote_write_allowed(1'b1),.ble_frame_seen(1'b0),.pad_active(7'd0),
  .force_levels(56'hc0a060c08040c0),.contrast(8'h7f),.capture_payload(payload),
  .oled_scl(scl),.oled_sda(sda),.ready(ready),.nack_seen(nack));
 oled_capture_columns ref_pixels(.clk(clk),.payload(dut.shown_capture),.timbre(dut.shown_timbre),
  .bank(dut.shown_bank),.pad(dut.shown_guide_target),.page(dut.page_index),.column(dut.column),.pixels(reference));
 assign sda=(dut.writer.state==4 || dut.writer.state==5 || dut.writer.state==9)?1'b0:1'bz;
 always @(posedge clk)if(rst_n && dut.tx_start && dut.phase==2)begin
  if(dut.page_index==0 && dut.column==0)begin
   last_stage=dut.shown_capture[15:8];bytes_seen=0;
  end
  if(dut.shown_capture[15:8]!=last_stage)$fatal(1,"capture snapshot tore within one frame");
  if(last_stage!=0 && (dut.page_index<4 || last_stage<10))begin
   if(dut.tx_payload!==reference)$fatal(1,"capture byte mux or ROM pipeline mismatch");
  end else if(dut.page_index>=4)begin
   if(dut.tx_payload!==dut.force_column(dut.page_index,dut.column,dut.shown_force_buckets))$fatal(1,"meters changed");
  end
  checks=checks+1;bytes_seen=bytes_seen+1;
  if(dut.page_index==7 && dut.column==127)begin
   if(bytes_seen!=1024)$fatal(1,"frame incomplete");frames=frames+1;
  end
 end
 initial begin
  payload[7:0]=1;payload[15:8]=1;payload[39:24]=120;payload[55:40]=400;payload[79:72]=255;payload[87:80]=160;
  repeat(3)@(negedge clk);rst_n=1;
  wait(dut.phase==2 && dut.page_index==2);payload[15:8]=3;payload[23:16]=68;
  wait(frames==2);payload[15:8]=10;
  wait(frames==3);payload[15:8]=0;
  wait(frames==4);
  if(nack)$fatal(1,"I2C slave did not acknowledge");
  $display("PASS: %0d actual OLED I2C bytes, frame snapshots, stage changes, seven meters and restore",checks);$finish;
 end
 initial begin #12000000;$fatal(1,"capture I2C frame timeout");end
endmodule
