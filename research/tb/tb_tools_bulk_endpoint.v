`timescale 1ns/1ps
module tb_tools_bulk_endpoint;
 reg clk=0,rst_n=0,rx_valid=0,tx_ready=0;reg[7:0]rx_byte=0;always #1 clk=~clk;
 wire tx_valid,request_valid,response_valid,bulk;wire[7:0]tx_byte,typ,len,bulk_byte;wire[111:0]payload,response;
 wire[6:0]index;wire[14:0]address;reg[7:0]memory_byte;integer k,count;reg[7:0]received[0:133],c;
 ble_control_endpoint #(.PRODUCT_TOOLS(1)) endpoint(.clk(clk),.rst_n(rst_n),.rx_valid(rx_valid),.rx_byte(rx_byte),.write_enable(1'b1),
  .key(4'd0),.bank(3'd2),.timbre(2'd1),.volume(5'd16),.vibrato(1'b0),.ui_state(2'd0),.song_index(8'd0),.guide_step(11'd0),.guide_target(3'd7),
  .guide_target_bank(3'd0),.playback_state(2'd0),.vibrato_depth(4'd0),.bend(8'd128),.led_mode(2'd0),.effect_mask(3'd0),.oled_contrast(8'd160),.pad_mask(7'd0),.telemetry(72'd0),
  .tx_valid(tx_valid),.tx_byte(tx_byte),.tx_ready(tx_ready),.tools_request_valid(request_valid),.tools_request_type(typ),.tools_request_length(len),.tools_request_payload(payload),
  .tools_response_valid(response_valid),.tools_response_payload(response),.tools_response_bulk(bulk),.tools_bulk_byte(bulk_byte),.tools_bulk_index(index));
 product_tools_engine engine(.clk(clk),.rst_n(rst_n),.link_active(1'b1),.interrupt(1'b0),.request_valid(request_valid),.request_type(typ),.request_length(len),.request_payload(payload),
  .response_valid(response_valid),.response_payload(response),.response_bulk(bulk),.bulk_index(index),.bulk_byte(bulk_byte),.record_address(address),.record_byte(memory_byte),
  .active_voices(6'd0),.deadline_fault(1'b0),.analysis_frame(16'd1),.analysis_ready(1'b0),.wave_data(512'd0),.spectrum_data(256'd0),.phase_data(512'd0),
  .recording(1'b0),.record_ready(1'b1),.record_samples(17'd400),.stored_token(16'h1234),.record_crc(16'h1234));
 always @(posedge clk)memory_byte<=address[7:0]^8'ha5;
 function[7:0]crc;input[7:0]p,d;integer i;reg[7:0]x;begin x=p^d;for(i=0;i<8;i=i+1)x=x[7]?(x<<1)^7:x<<1;crc=x;end endfunction
 task send;input[7:0]x;begin @(negedge clk);rx_valid=1;rx_byte=x;@(negedge clk);rx_valid=0;end endtask
 initial begin repeat(4)@(negedge clk);rst_n=1;
  c=0;send(8'ha5);send(1);c=crc(c,1);send(8'h55);c=crc(c,8'h55);send(9);c=crc(c,9);send(4);c=crc(c,4);
  send(8'h34);c=crc(c,8'h34);send(8'h12);c=crc(c,8'h12);send(123);c=crc(c,123);send(0);c=crc(c,0);send(c);
  wait(tx_valid);for(k=0;k<134;k=k+1)begin
   repeat(6)@(negedge clk);if(!tx_valid)$fatal(1,"bulk frame stopped early");received[k]=tx_byte;tx_ready=1;@(negedge clk);tx_ready=0;
  end
  repeat(3)@(negedge clk);if(tx_valid)$fatal(1,"bulk frame did not end");
  if(received[2]!=8'h86 || received[3]!=9 || received[4]!=128 || received[5]!=1 || received[6]!=8'h55 || received[7]!=0 || received[8]!=123)$fatal(1,"bulk header");
  for(k=0;k<123;k=k+1)if(received[k+10]!==((123+k<200)?((123+k)^8'ha5)&255:0))$fatal(1,"bulk byte %d got=%h",k,received[k+10]);
  c=0;for(k=1;k<133;k=k+1)c=crc(c,received[k]);if(c!=received[133])$fatal(1,"bulk streaming CRC");
  $display("PASS:actual endpoint134-byte bulk frame, correlated sequence, registered RAM, padded final data and streaming CRC8");$finish;
 end
 initial begin #100000;$fatal(1,"bulk timeout");end
endmodule
