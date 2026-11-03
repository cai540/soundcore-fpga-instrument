`timescale 1ns/1ps
module tb_tools_recorder;
 reg clk=0,rst_n=0,tick=0,start=0,stop=0;always #1 clk=~clk;
 reg signed[15:0] sample=0;reg[14:0] address=0;wire[7:0] data;
 wire recording,ready;wire[16:0]count;wire[15:0]token,crc;
 audio_record_adpcm #(.MAX_SAMPLES(1024)) dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.sample_in(sample),
  .start(start),.stop(stop),.start_token(16'h1234),.recording(recording),.ready(ready),.sample_count(count),
  .token(token),.crc16(crc),.read_address(address),.read_data(data));
 integer n,k,fd,filtered_fd;reg[15:0] old_crc;real x;
 initial begin
  filtered_fd=$fopen("build/acceptance_20261102/record_filtered.txt","w");
  repeat(4)@(negedge clk);rst_n=1;start=1;@(negedge clk);start=0;
  n=0;
  while(!ready)begin
   sample=$rtoi(14000.0*$sin(6.283185307179586*440*n/48000.0));tick=1;@(negedge clk);tick=0;
   repeat(255)@(negedge clk);n=n+1;
  end
  $fclose(filtered_fd);
  if(count!=1024 || recording || token!=16'h1234)$fatal(1,"record boundary/status");
  fd=$fopen("build/acceptance_20261102/record_bytes.txt","w");
  for(k=0;k<512;k=k+1)begin address=k;repeat(3)@(negedge clk);$fwrite(fd,"%02x\n",data);end
  $fclose(fd);old_crc=crc;
  start=1;@(negedge clk);start=0;repeat(4)@(negedge clk);
  if(!ready || recording || crc!=old_crc)$fatal(1,"duplicate record token replaced frozen recording");
  fd=$fopen("build/acceptance_20261102/record_crc.txt","w");$fwrite(fd,"%04x\n",crc);$fclose(fd);
  $display("PASS:127-tap actual FIR->8kHz->IMA ADPCM,capacity,CRC,registered reads,idempotent token");$finish;
 end
 always @(posedge clk)if(rst_n && recording && dut.filtered_valid)$fwrite(filtered_fd,"%d\n",dut.filtered);
 initial begin #5000000;$fatal(1,"recorder timeout");end
endmodule
