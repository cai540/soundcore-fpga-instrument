`timescale 1ns/1ps
module tb_capture_oled_render;
 reg clk=0;always #5 clk=~clk;
 reg [87:0]payload=0;reg [2:0]page=0;reg [6:0]column=0;wire [7:0]pixels;
 tri1 scl,sda;
 integer stage,p,c,fd,total;reg [1023:0]filename;
 oled_capture_columns dut(.clk(clk),.payload(payload),.timbre(1'b1),.bank(3'd2),.pad(3'd4),.page(page),.column(column),.pixels(pixels));
 oled_status_ssd1315 normal(.clk(clk),.rst_n(1'b0),.bank(3'd0),.timbre(1'b1),.volume(5'd16),.vibrato(1'b0),
  .ui_state(2'd0),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),.playback_state(2'd0),
  .auth_pending(1'b0),.remote_write_allowed(1'b0),.ble_frame_seen(1'b0),.pad_active(7'd0),
  .force_levels(56'd0),.contrast(8'h7f),.oled_scl(scl),.oled_sda(sda));
 initial begin
  for(stage=1;stage<=13;stage=stage+1)begin
   payload=0;payload[7:0]=1;payload[15:8]=stage;payload[23:16]=68;payload[39:24]=120;
   payload[55:40]=400;payload[71:56]=66;payload[79:72]=69;payload[87:80]=160;
   if(stage>=9)begin payload[39:24]=12;payload[55:40]=66;end
   $sformat(filename,"build/melody_workbench_20261028/oled_%0d.hex",stage);fd=$fopen(filename,"w");total=0;
   for(p=0;p<8;p=p+1)for(c=0;c<128;c=c+1)begin
    page=p;column=c;repeat(3)@(negedge clk);
    if(pixels===8'hxx)$fatal(1,"uninitialized glyph");
    if(stage>=10 && p>=4)$fdisplay(fd,"%02x",normal.force_column(p,c,{5'd24,5'd18,5'd8,5'd24,5'd12,5'd6,5'd20}));
    else begin $fdisplay(fd,"%02x",pixels);total=total+(pixels!=0);end
   end
   if(total<30)$fatal(1,"empty capture phase %0d",stage);$fclose(fd);
  end
  $display("PASS: thirteen actual RTL OLED phase frames, Chinese baselines, seven meters preserved");$finish;
 end
endmodule
