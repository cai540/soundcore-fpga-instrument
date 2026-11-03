`timescale 1ns/1ps
module tb_handpan_control;
reg clk=0,rst_n=0,rx_valid=0,tx_ready=0,k3=1;
reg enc_s1=1,enc_s2=1,enc_key=1;
always #5 clk=~clk;
reg[7:0]rx_byte=0;
wire remote_valid,tx_valid;wire[7:0]typ,value,value2,tx_byte;
wire[111:0]payload;wire[1:0]tone;
ble_control_endpoint #(.EXTENDED_STATE(1),.SONG_EXTENSIONS(1),.HANDPAN_ENABLE(1)) dut(
 .clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),.tx_ready(tx_ready),.write_enable(1'b1),
 .key(4'd0),.bank(3'd2),.timbre(tone),.volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),.song_index(8'd0),
 .guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),.playback_state(2'd0),.vibrato_depth(4'd4),
 .bend(8'd128),.led_mode(2'd0),.effect_mask(3'd0),.oled_contrast(8'd127),.pad_mask(7'd0),.telemetry(72'd0),
 .remote_valid(remote_valid),.remote_type(typ),.remote_value(value),.remote_value2(value2),.remote_payload(payload),
 .tx_valid(tx_valid),.tx_byte(tx_byte));
front_panel_product #(.HANDPAN_ENABLE(1),.DEBOUNCE_CYCLES(2),.LONG_PRESS_CYCLES(12),.DEPTH_TIMEOUT_CYCLES(200)) panel(
 .clk(clk),.rst_n(rst_n),.bank_down_n(1'b1),.bank_up_n(1'b1),.timbre_n(k3),.song_back_n(1'b1),.play_pause_n(1'b1),
 .enc_s1_n(enc_s1),.enc_s2_n(enc_s2),.enc_key_n(enc_key),.remote_valid(remote_valid),.remote_type(typ),
 .remote_value(value),.remote_payload(payload[55:0]),.player_finished(1'b0),.guide_finished(1'b0),.timbre_select(tone));
function[7:0]crc;input[7:0]a,b;reg[7:0]c;integer j;
begin c=a^b;for(j=0;j<8;j=j+1)c=c[7]?(c<<1)^8'h07:c<<1;crc=c;end endfunction
task send;input[7:0]b;begin @(negedge clk);rx_byte=b;rx_valid=1;@(negedge clk);rx_valid=0;end endtask
task frame;input[7:0]t,s,l;input[111:0]data;reg[7:0]c;integer j;begin
 c=0;send(8'ha5);send(1);c=crc(c,1);send(t);c=crc(c,t);send(s);c=crc(c,s);send(l);c=crc(c,l);
 for(j=0;j<l;j=j+1)begin send(data[j*8+:8]);c=crc(c,data[j*8+:8]);end
 send(c);repeat(8)@(negedge clk);
end endtask
task drain;begin tx_ready=1;while(tx_valid)@(negedge clk);tx_ready=0;end endtask
task button;input[1:0]expected;begin
 @(negedge clk);k3=0;repeat(12)@(negedge clk);k3=1;repeat(12)@(negedge clk);
 if(tone!==expected)$fatal(1,"K3 cycle got %d expected %d",tone,expected);
end endtask
reg[111:0]scene;
integer bank,pad,key;reg[2:0]map_bank,map_pad;reg[3:0]map_key;wire[6:0]map_note;wire map_valid;
handpan_pitch_layout map(.bank(map_bank),.pad(map_pad),.key(map_key),.note_index(map_note),.valid(map_valid));
initial begin
 repeat(3)@(negedge clk);rst_n=1;repeat(3)@(negedge clk);
 button(0);button(2);button(3);button(1);
 frame(8'h12,1,1,3);if(tone!=3 || dut.snapshot[15:8]!=3 || dut.response_error)$fatal(1,"style SET/STATE not applied");
 drain();frame(8'h12,2,1,4);if(tone!=3 || !dut.response_error)$fatal(1,"bad tone accepted");
 drain();scene=0;scene[7:0]=2;scene[15:8]=2;scene[23:16]=16;scene[39:32]=4;scene[55:48]=160;
 frame(8'h1f,3,7,scene);if(tone!=2 || dut.snapshot[15:8]!=2)$fatal(1,"handpan scene truncated");drain();
 frame(8'h12,4,1,1);if(tone!=1 || dut.snapshot[15:8]!=1)$fatal(1,"melodic restore failed");
 drain();frame(8'h12,5,1,3);
 @(negedge clk);enc_key=0;repeat(24)@(negedge clk);enc_key=1;repeat(8)@(negedge clk);
 if(!panel.depth_edit)$fatal(1,"metal long press did not open drive edit");
 enc_s1=0;repeat(10)@(negedge clk);enc_s1=1;repeat(10)@(negedge clk);
 if(panel.vibrato_depth!=5 || panel.volume_level!=16)$fatal(1,"encoder drive edit changed wrong control");
 for(bank=0;bank<5;bank=bank+1)for(key=0;key<12;key=key+1)for(pad=0;pad<7;pad=pad+1)begin
  map_bank=bank;map_key=key;map_pad=pad;#1;
  if(!map_valid || map_note>=72)$fatal(1,"unplayable handpan voicing");
  if(bank==2 && key==0)case(pad)
   0:if(map_note!=24)$fatal;1:if(map_note!=26)$fatal;2:if(map_note!=28)$fatal;
   3:if(map_note!=31)$fatal;4:if(map_note!=33)$fatal;5:if(map_note!=36)$fatal;6:if(map_note!=38)$fatal;
  endcase
 end
 $display("PASS: K3 four tones, scene/STATE, physical knob drive edit, legacy restore and 420 playable voicings");$finish;
end
endmodule
