`timescale 1ns/1ps
module audio_pll_12m288(input wire clkin,output wire clk_audio,locked);
 assign clk_audio=clkin;assign locked=1'b1;
endmodule
// Boundary-injection integration test of real product top-level LED routing.
// Does not claim to be a physical-button or power-on hardware measurement.
module tb_contest_guide_top;
 reg clk=0,rst_n=0;always #5 clk=~clk;wire[6:0]led;
 GSR GSR(.GSRI(rst_n));
 pressure_i2s_panel_oled_ble_experiment_top #(.PRODUCT_TOOLS(1),.UPLOADED_SCORE_ENABLE(1),
  .EARLY_FORCE_ENABLE(1),.CONTINUOUS_EXPRESSION(1),.HANDPAN_ENABLE(1)) dut(.sys_clk(clk),.rst_n(rst_n),
  .adc_miso(1'b0),.enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
  .panel_bank_down_n(1'b1),.panel_bank_up_n(1'b1),.panel_timbre_n(1'b1),
  .panel_song_back_n(1'b1),.panel_play_pause_n(1'b1),.ble_uart_rx(1'b1),.pad_led_o(led));
 task cycles;input integer n;integer i;begin for(i=0;i<n;i=i+1)@(negedge clk);end endtask
 initial begin
  force dut.native_guidance_active=0;force dut.remote_valid=0;
  force dut.guide_target_led=7'd4;force dut.performance_led=7'd2;
  cycles(3);rst_n=1;cycles(4);if(dut.led_mode!=0)$fatal(1,"default mode");
  force dut.native_guidance_active=1;cycles(3);
  if(dut.led_mode!=1 || led!=4)$fatal(1,"offline entry did not enable guide routing");
  force dut.remote_valid=1;force dut.remote_type=8'h1d;force dut.remote_value=0;cycles(2);
  force dut.remote_valid=0;cycles(2);
  if(dut.led_mode!=0 || led!=2)$fatal(1,"explicit follow mode did not take priority");
  force dut.native_guidance_active=0;cycles(2);if(dut.led_mode!=0)$fatal(1,"exit restore failed");
  force dut.remote_valid=1;force dut.remote_value=3;cycles(2);force dut.remote_valid=0;
  force dut.native_guidance_active=1;cycles(3);if(dut.led_mode!=1)$fatal(1,"second guide entry");
  force dut.native_guidance_active=0;cycles(2);if(dut.led_mode!=3)$fatal(1,"previous breath mode not restored");
  $display("PASS: actual top routing, offline entry/restore and explicit App-follow priority");$finish;
 end
endmodule
