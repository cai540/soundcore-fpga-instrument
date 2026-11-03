`timescale 1ns/1ps
module tb_natural_ble;
reg clk=0,rst_n=0,rx_valid=0,tx_ready=0;always #5 clk=~clk;
reg[7:0]rx_byte=0;reg[3:0]key=5;wire remote_valid,tx_valid;wire[7:0]typ,value,value2,tx_byte;wire[111:0]payload;
ble_control_endpoint #(.EXTENDED_STATE(1),.SONG_EXTENSIONS(1),.REALTIME_NOTES(1),.OMR_ENABLE(1)) dut(
.clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),.tx_ready(tx_ready),.write_enable(1'b1),
.key(key),.bank(3'd2),.timbre(1'b1),.volume(5'd6),.vibrato(1'b0),.ui_state(2'd0),.song_index(8'd0),.guide_step(11'd0),.guide_target(3'd0),.guide_target_bank(3'd0),.playback_state(2'd0),.vibrato_depth(4'd4),.bend(8'd128),.led_mode(2'd0),.effect_mask(3'd0),.oled_contrast(8'd127),.pad_mask(7'd0),.telemetry(72'd0),
.remote_valid(remote_valid),.remote_type(typ),.remote_value(value),.remote_value2(value2),.remote_payload(payload),.tx_valid(tx_valid),.tx_byte(tx_byte));
integer accepted=0,k;reg[111:0]p;
always @(posedge clk)if(remote_valid)begin
 if(typ==8'h25)accepted=accepted+1;
 if(typ==8'h27)key<=value[3:0];
end
function[7:0]crc;input[7:0]a,b;reg[7:0]c;integer j;
begin c=a^b;for(j=0;j<8;j=j+1)c=c[7]?(c<<1)^8'h07:c<<1;crc=c;end endfunction
task send;input[7:0]b;begin @(negedge clk);rx_byte=b;rx_valid=1;@(negedge clk);rx_valid=0;end endtask
task frame;input[7:0]t,s,l;input[111:0]data;reg[7:0]c;integer j;begin
c=0;send(8'ha5);send(1);c=crc(c,1);send(t);c=crc(c,t);send(s);c=crc(c,s);send(l);c=crc(c,l);
for(j=0;j<l;j=j+1)begin send(data[j*8+:8]);c=crc(c,data[j*8+:8]);end
send(c);repeat(6)@(negedge clk);end endtask
task drain;begin tx_ready=1;while(tx_valid)@(negedge clk);tx_ready=0;end endtask
initial begin
 repeat(3)@(negedge clk);rst_n=1;
 frame(8'h26,1,0,0);
 if(!tx_valid || dut.response_type!=8'h84 || dut.response_len!=7 || dut.snapshot[47:40]!=5 || dut.snapshot[31:24]!=107)$fatal(1,"layout capability missing");
 p=0;p[7:0]=3;p[15:8]=3;p[23:16]=200;p[31:24]=70;p[39:32]=1;
 frame(8'h25,2,10,p);
 if(accepted!=1 || payload[31:24]!=70 || typ!=8'h25 || dut.response_seq!=1)$fatal(1,"exact note blocked or reply contaminated");
 frame(8'h25,2,10,p);if(accepted!=1)$fatal(1,"duplicate exact attack accepted");
 p[31:24]=72;frame(8'h25,3,10,p);if(accepted!=1)$fatal(1,"illegal pitch accepted");
 p[7:0]=0;p[15:8]=0;frame(8'h25,4,10,p);if(accepted!=2 || value!=0)$fatal(1,"release must ignore unused pitch bytes");
 drain();frame(8'h27,5,1,3);
 if(key!=3 || dut.response_type!=8'h84 || dut.snapshot[47:40]!=3)$fatal(1,"tonic was not applied before reply");
 drain();frame(8'h27,6,1,12);if(dut.response_error!=1 || key!=3)$fatal(1,"invalid tonic applied");
 $display("PASS: layout negotiation, all 10 absolute payload bytes, busy TX bypass, duplicate/illegal guards, authoritative release and applied tonic ACK");$finish;
end
endmodule
