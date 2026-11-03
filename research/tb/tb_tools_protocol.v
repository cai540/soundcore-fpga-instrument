`timescale 1ns/1ps
module tb_tools_protocol;
 reg clk=0,rst_n=0,request=0,link=1,irq=0;always #1 clk=~clk;
 reg[7:0]typ=0,len=0;reg[111:0]payload=0;wire valid;wire[111:0]reply;
 wire diag,map,clear,start,stop;wire[31:0]gates;wire[223:0]notes;wire[48:0]mapping;wire[1:0]view;
 wire[15:0]token;wire[14:0]address;reg[7:0]data;
 product_tools_engine dut(.clk(clk),.rst_n(rst_n),.link_active(link),.interrupt(irq),
  .request_valid(request),.request_type(typ),.request_length(len),.request_payload(payload),.response_valid(valid),.response_payload(reply),
  .active_voices(6'd32),.deadline_fault(1'b0),.analysis_frame(16'd9),.analysis_ready(1'b1),
  .wave_data({64{8'h55}}),.spectrum_data({32{8'h33}}),.phase_data({64{8'h77}}),
  .diag_enabled(diag),.diag_gate(gates),.diag_notes(notes),.view_mode(view),.map_enabled(map),.pad_map(mapping),.clear_voices(clear),
  .record_start(start),.record_stop(stop),.record_token(token),.recording(1'b0),.record_ready(1'b1),
  .record_samples(17'd36),.stored_token(16'h1234),.record_crc(16'habcd),.record_address(address),.record_byte(data));
 always @(posedge clk)data<=address[7:0]^8'ha5;
 task cmd;input[7:0]t,l;input[111:0]p;integer timeout;
 begin @(negedge clk);typ=t;len=l;payload=p;request=1;@(negedge clk);request=0;
  timeout=0;while(!valid && timeout<60)begin @(negedge clk);timeout=timeout+1;end
  if(!valid || reply[7:0]!=1 || reply[15:8]!=t)$fatal(1,"tool response missing");
 end endtask
 integer i;reg[111:0]m;reg[48:0]previous;
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  cmd(8'h41,1,0);if(clear)$fatal(1,"idle diagnostic stop cleared ordinary voices");
  cmd(8'h41,1,4);if(gates!=15)$fatal(1,"4 voice mask");
  cmd(8'h41,1,8);if(gates!=255)$fatal(1,"8 voice mask");
  cmd(8'h41,1,16);if(gates!=65535)$fatal(1,"16 voice mask");
  cmd(8'h41,1,32);if(!diag || gates!=32'hffffffff)$fatal(1,"32 diagnosis not enabled");
  cmd(8'h42,3,{88'd0,8'd0,8'd30,8'd3});if(gates[3])$fatal(1,"independent gate");
  cmd(8'h42,3,{88'd0,8'd1,8'd60,8'd3});if(!gates[3] || notes[21+:7]!=60)$fatal(1,"independent pitch");
  m=1;for(i=0;i<7;i=i+1)m[8+i*8 +: 8]=24+i;
  cmd(8'h46,8,m);if(!map || mapping[0+:7]!=24)$fatal(1,"map not applied");previous=mapping;
  m[15:8]=100;cmd(8'h46,8,m);if(reply[23:16]!=3 || mapping!=previous)$fatal(1,"invalid map not atomic");
  cmd(8'h44,3,{88'd0,16'h2001,8'd0});if(reply[39:32]!=64)$fatal(1,"snapshot length");
  cmd(8'h45,4,{80'd0,16'd0,16'h2001});if(reply[111:40]!={9{8'h55}})$fatal(1,"snapshot bytes");
  cmd(8'h45,4,{80'd0,16'd63,16'h2001});if(reply[47:40]!=8'h55 || reply[111:48]!=0)$fatal(1,"snapshot final-byte padding");
  cmd(8'h53,4,{80'd0,16'd4,16'h1234});
  for(i=0;i<9;i=i+1)if(reply[40+i*8+:8]!=((4+i)^8'ha5))$fatal(1,"record offset byte%0d got%h",i,reply[40+i*8+:8]);
  cmd(8'h53,4,{80'd0,16'd4,16'h1235});if(reply[23:16]!=6)$fatal(1,"token guard");
  cmd(8'h41,1,0);if(diag || gates!=0)$fatal(1,"diagnosis exit");
  cmd(8'h43,1,3);if(view!=3)$fatal(1,"display not selected");
  irq=1;@(negedge clk);irq=0;if(view!=0 || diag)$fatal(1,"panel interrupt did not leave diagnostic display");
  cmd(8'h41,1,4);cmd(8'h43,1,2);link=0;@(negedge clk);if(diag || gates!=0 || view!=0)$fatal(1,"link loss safety");link=1;
  $display("PASS:actual tool endpoints,4/8/16/32 independent gates,pitch,atomic maps,snapshot/audio tokens,panel/link safety,non-destructive idle stop");$finish;
 end
endmodule
