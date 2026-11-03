`timescale 1ns/1ps
// Uses the actual product top, allocator, audio, OLED and LED wiring. Only
// the vendor PLL and UART electrical serialization are bypassed in simulation.
module audio_pll_12m288(input clkin,output clk_audio,output locked);
 assign clk_audio=clkin;assign locked=1'b1;
endmodule
module tb_melody_product_integration;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,rx_valid=0;reg[7:0]rx_byte=0;
 wire[6:0]leds;tri1 scl,sda;
 integer checks=0,k,t,sounding=0;reg[7:0]seq=0;reg[15:0]crc;
 reg[23:0]words[0:2];reg[111:0]payload;
 pressure_i2s_panel_oled_ble_experiment_top #(.HEADPHONE_OUTPUT(1),.EARLY_FORCE_ENABLE(1),
  .CONTINUOUS_EXPRESSION(1),.UPLOADED_SCORE_ENABLE(1)) dut(
  .sys_clk(clk),.rst_n(rst_n),.adc_miso(1'b0),
  .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
  .panel_bank_down_n(1'b1),.panel_bank_up_n(1'b1),.panel_timbre_n(1'b1),
  .panel_song_back_n(1'b1),.panel_play_pause_n(1'b1),.ble_uart_rx(1'b1),
  .oled_scl(scl),.oled_sda(sda),.pad_led_o(leds));
 defparam dut.runtime_score.engine.CYCLES_PER_MS=256;
 function[7:0]cb;input[7:0]a,b;reg[7:0]c;integer j;
 begin c=a^b;for(j=0;j<8;j=j+1)c=c[7]?(c<<1)^8'h07:c<<1;cb=c;end endfunction
 function[15:0]cw;input[15:0]a;input[7:0]b;reg[15:0]c;integer j;
 begin c=a^{b,8'd0};for(j=0;j<8;j=j+1)c=c[15]?(c<<1)^16'h1021:c<<1;cw=c;end endfunction
 task check;input condition;input[511:0]msg;
 begin checks=checks+1;if(!condition)$fatal(1,"%s",msg);end endtask
 task send;input[7:0]b;
 begin @(negedge clk);rx_valid=1;rx_byte=b;@(negedge clk);rx_valid=0;end endtask
 task request;input[7:0]typ,len;input[111:0]p;reg[7:0]c;integer j,n;
 begin seq=seq+1;c=cb(cb(cb(cb(0,1),typ),seq),len);
  send(8'ha5);send(1);send(typ);send(seq);send(len);
  for(j=0;j<len;j=j+1)begin send(p[8*j+:8]);c=cb(c,p[8*j+:8]);end
  send(c);
  if(typ==8'h24)begin repeat(8)@(negedge clk);end
  else begin
  n=0;while(!dut.uart_tx_valid && n<100)begin @(negedge clk);n=n+1;end
  check(dut.uart_tx_valid,"response timeout");
  check(dut.uart_tx_byte==8'ha5,"response header");
  n=0;while(dut.uart_tx_valid && n<25)begin @(negedge clk);n=n+1;end
  check(n<25,"response length");repeat(3)@(negedge clk);end
 end endtask
 task action;input[7:0]a;begin request(8'h34,1,a);repeat(4)@(negedge clk);end endtask
 task phone;input[6:0]mask;begin payload=0;payload[6:0]=mask;payload[14:8]=mask;
  payload[23:16]=176;request(8'h24,3,payload);end endtask
 always @(negedge clk)if(rst_n && dut.audio_core.sample_tick && dut.audio_core.autoplay_sample!==16'd0)
  sounding=sounding+1;
 initial begin
  force dut.uart_rx_valid=rx_valid;force dut.uart_rx_byte=rx_byte;force dut.uart_tx_ready=1'b1;
  repeat(5)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);
  request(8'h01,0,0);request(8'h11,1,2);request(8'h12,1,0);request(8'h1d,1,1);
  words[0]=(200<<6);words[1]=(100<<6)|7;words[2]=(300<<6)|(4<<3)|6;
  crc=16'hffff;for(k=0;k<3;k=k+1)crc=cw(cw(cw(crc,words[k][7:0]),words[k][15:8]),words[k][23:16]);
  payload=0;payload[15:0]=16'h4321;payload[31:16]=3;payload[47:32]=crc;payload[55:48]=1;
  request(8'h31,7,payload);payload=0;payload[15:0]=16'h4321;
  for(k=0;k<3;k=k+1)payload[32+24*k+:24]=words[k];request(8'h32,13,payload);
  request(8'h33,2,16'h4321);check(dut.score_ready,"ready after commit");
  action(1);
  check(dut.score_gate && dut.audio_core.autoplay_note_index==0 && dut.visual_timbre==1,"autoplay audio/config routing");
  check(dut.visual_force_levels[7:0]==224 && dut.display.force_levels[7:0]==224,"OLED playback force meter");
  check(leds==1 && !dut.lyric_mode,"uploaded melody LEDs without unrelated built-in lyrics");
  t=0;while(dut.score_step==0 && t<60000)begin @(negedge clk);t=t+1;end
  repeat(4)@(negedge clk);check(dut.score_step==1 && !dut.score_gate && dut.visual_force_levels==0,"rest is silent and meter blank");
  check(sounding>0,"actual synthesizer generated samples");
  t=0;while(dut.score_step==1 && t<30000)begin @(negedge clk);t=t+1;end
  repeat(4)@(negedge clk);
  check(dut.score_note==34 && dut.audio_core.autoplay_note_index==34 && dut.visual_bank==4,"last pitch and display bank");
  check(leds==7'h40 && dut.visual_force_levels[55:48]==224,"last key LEDs/meter");
  t=0;while(!dut.score_finished && t<85000)begin @(negedge clk);t=t+1;end
  check(dut.score_finished && dut.visual_bank==2 && dut.visual_timbre==0,"configuration restored on autoplay end");
  action(4);check(dut.score_guiding && dut.guide_bank==0 && dut.audio_core.panel_timbre==1,"guide applies score bank/timbre");
  phone(2);check(dut.score_step==0,"wrong phone pad does not advance");phone(0);
  phone(1);repeat(8)@(negedge clk);
  check(dut.score_step==2 && dut.guide_bank==4 && dut.display.guide_target==6,"one phone hit advances past rest and switches bank");
  // The allocator must retain the OLD target pitch when the guide advances.
  t=0;while(dut.audio_core.allocator.pending!=0 && t<300)begin @(negedge clk);t=t+1;end
  check(dut.audio_core.note_index[5:0]==1 && dut.audio_core.note_index[11:6]==0,"phone strikes use target bank at acceptance");
  phone(0);phone(7'h40);repeat(8)@(negedge clk);
  check(dut.score_finished && dut.guide_bank==2 && dut.audio_core.panel_timbre==0 && dut.display.ui_state==0,
   "guide end restores normal audio and OLED configuration");
  action(4);
  force dut.strike_event=1'b1;force dut.strike_channel=3'd0;@(negedge clk);
  release dut.strike_event;release dut.strike_channel;repeat(8)@(negedge clk);
  check(dut.score_step==2 && dut.guide_bank==4,"physical strike advances guide once");
  request(8'h23,1,1);check(!dut.score_engaged && dut.autoplay_active,"built-in song takes control again");
  $display("PASS: %0d full product routing checks: audio, bank-at-strike, phone/physical guide, OLED/LED, restore, built-in handoff",checks);$finish;
 end
 initial begin #2500000;$fatal(1,"global timeout");end
endmodule
