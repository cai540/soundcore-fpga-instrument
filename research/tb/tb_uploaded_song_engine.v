`timescale 1ns/1ps
module tb_uploaded_song_engine;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,link_active=1,request_valid=0,stop_external=0,strike_valid=0;
 reg[2:0]strike_pad=0;reg[7:0]request_type=0,request_seq=0,request_length=0;
 reg[111:0]request_payload=0;wire response_valid;wire[111:0]response_payload;
 wire playing,paused,guiding,finished,timbre,start_pulse,ready,gate;
 wire[9:0]step;wire[2:0]bank,pad;wire[5:0]note;wire[6:0]guide_led;
 uploaded_song_engine #(.CYCLES_PER_MS(10),.UPLOAD_TIMEOUT_MS(80)) dut(.*);
 integer checks=0,i,j,n;reg[111:0]p;reg[15:0]crc,old_crc;reg[23:0]words[0:511];
 function[15:0] cb;input[15:0]c0;input[7:0]b;reg[15:0]c;integer k;
 begin c=c0^{b,8'd0};for(k=0;k<8;k=k+1)c=c[15]?(c<<1)^16'h1021:c<<1;cb=c;end endfunction
 function[23:0] ev;input integer ms,nt;begin ev=(ms<<6)|(nt<0?7:((nt/7)<<3)|(nt%7));end endfunction
 task check;input condition;input[511:0]msg;begin checks=checks+1;if(!condition)$fatal(1,"%s",msg);end endtask
 task req;input[7:0]typ,len;input[111:0]payload;integer t;begin
  @(negedge clk);request_valid=1;request_type=typ;request_length=len;request_payload=payload;request_seq=request_seq+1;
  @(negedge clk);request_valid=0;t=0;
  while(!response_valid && t<50)begin @(negedge clk);t=t+1;end
  check(response_valid,"response timeout");@(negedge clk);
 end endtask
 task action;input[7:0]v;begin req(8'h34,1,v);end endtask
 task begin_score;input[15:0]tok;input integer count;input[15:0]c;begin
  p=0;p[15:0]=tok;p[31:16]=count;p[47:32]=c;p[55:48]=1;req(8'h31,7,p);
 end endtask
 task data3;input[15:0]tok;input integer index,count;begin
  p=0;p[15:0]=tok;p[31:16]=index;
  for(j=0;j<count;j=j+1)p[32+24*j+:24]=words[index+j];
  req(8'h32,4+count*3,p);
 end endtask
 task hash_words;input integer count;begin crc=16'hffff;
  for(i=0;i<count;i=i+1)crc=cb(cb(cb(crc,words[i][7:0]),words[i][15:8]),words[i][23:16]);end endtask
 initial begin
  repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
  action(1);check(response_payload[23:16]==6 && !playing,"cannot play empty score");
  words[0]=ev(200,0);words[1]=ev(100,-1);words[2]=ev(300,34);hash_words(3);old_crc=crc;
  begin_score(16'h1234,3,crc);check(response_payload[9] && response_payload[39:24]==0,"begin");
  data3(16'h1234,0,3);check(response_payload[39:24]==3,"all events staged");
  data3(16'h1234,0,3);check(response_payload[39:24]==3 && response_payload[23:16]==0,"duplicate chunk idempotent");
  req(8'h33,2,16'h1234);check(ready && response_payload[95:80]==old_crc,"atomic commit CRC");
  req(8'h33,2,16'h1234);check(response_payload[23:16]==0 && ready,"commit retry idempotent");
  action(1);repeat(4)@(negedge clk);check(gate && note==0,"first event loaded");
  action(2);check(paused && !gate,"paused silence");repeat(300)@(negedge clk);
  check(step==0,"pause freezes progress");action(3);check(!paused,"resume");
  begin_score(16'h2222,3,crc);check(response_payload[23:16]==2 && ready,"no overwrite while playing");
  n=0;while(step==0 && n<2500)begin @(negedge clk);n=n+1;end
  repeat(3)@(negedge clk);check(step==1 && !gate,"rest timed, no sound");
  n=0;while(!finished && n<5000)begin @(negedge clk);n=n+1;end
  check(finished && step==3 && !gate,"autonomous complete");
  action(4);repeat(4)@(negedge clk);check(guiding && guide_led==1,"guide first pad");
  @(negedge clk);strike_valid=1;strike_pad=1;@(negedge clk);strike_valid=0;
  check(step==0,"wrong pad does not advance");
  @(negedge clk);strike_valid=1;strike_pad=0;@(negedge clk);strike_valid=0;
  repeat(10)@(negedge clk);check(step==2 && bank==4 && pad==6,"guide skips rest and automatic bank");
  @(negedge clk);strike_valid=1;strike_pad=6;@(negedge clk);strike_valid=0;
  repeat(3)@(negedge clk);check(finished && step==3 && guide_led==0,"one correct strike per note");action(0);
  begin_score(16'h2222,3,old_crc^16'd1);data3(16'h2222,0,3);req(8'h33,2,16'h2222);
  check(response_payload[23:16]==5 && ready && response_payload[95:80]==old_crc,"bad CRC preserves published score");
  begin_score(16'h3333,3,old_crc);data3(16'h3333,2,1);
  check(response_payload[23:16]==4 && response_payload[39:24]==0,"out of order rejected");
  link_active=0;repeat(25)@(negedge clk);check(!dut.receiving && ready,"link loss cancels only staging");link_active=1;
  begin_score(16'h4444,3,old_crc);repeat(820)@(negedge clk);
  check(!dut.receiving && ready,"timeout preserves published score");
  begin_score(16'h5555,3,old_crc);req(8'h35,2,16'h5555);check(!dut.receiving && ready,"abort preserves score");
  words[0]=(20<<6)|(5<<3);begin_score(16'h5556,1,0);data3(16'h5556,0,1);
  check(response_payload[23:16]==1 && !dut.receiving && ready,"invalid bank rejected");
  for(i=0;i<512;i=i+1)words[i]=ev(20,i%35);hash_words(512);
  begin_score(16'h6789,512,crc);
  for(i=0;i<512;i=i+3)begin n=512-i;if(n>3)n=3;data3(16'h6789,i,n);end
  check(dut.received==512,"512 event boundary");req(8'h33,2,16'h6789);
  check(ready && response_payload[39:24]==512,"max score commit");
  action(1);n=0;while(!finished && n<110000)begin @(negedge clk);n=n+1;end
  check(finished && step==512,"max score playback completion");
  $display("PASS: %0d upload/RAM/playback/guide checks",checks);$finish;
 end
 initial begin #3000000;$fatal(1,"global timeout");end
endmodule
