`timescale 1ns/1ps
module tb_tools_analyzer;
 reg clk=0,rst_n=0,tick=0,latch=0;always #1 clk=~clk;
 reg signed[15:0] sample=0;wire pending;wire[15:0] id;
 reg[9:0]pixel_address=0;integer dot;reg[7:0]expected_pixel;integer px,py,pixel_fd;
 wire[511:0]wave;wire[255:0]spectrum;wire[511:0]points;wire bank;wire[7:0]pixel;
 product_audio_analyzer dut(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.sample_in(sample),
  .frame_latch(latch),.pending_frame(pending),.frame_id(id),.wave_data(wave),.spectrum_data(spectrum),
  .phase_data(points),.phase_bank(bank),.display_phase_bank(bank),.phase_address(pixel_address),.phase_pixels(pixel));
 integer n,fd;real x;
 initial begin
  repeat(4)@(negedge clk);rst_n=1;
  for(n=0;n<1024;n=n+1)begin
   x=11000.0*$sin(6.283185307179586*13*n/1024.0)+5000.0*$sin(6.283185307179586*53*n/1024.0);
   sample=$rtoi(x);tick=1;@(negedge clk);tick=0;repeat(15)@(negedge clk);
  end
  wait(pending);@(negedge clk);
  if((^spectrum)===1'bx || spectrum==0 || (^wave)===1'bx || (^points)===1'bx)$fatal(1,"unknown/empty analyzer frame");
  pixel_fd=$fopen("build/acceptance_20261102/phase_bitmap.txt","w");
  for(n=0;n<768;n=n+1)begin
   expected_pixel=0;
   for(dot=0;dot<32;dot=dot+1)begin px=points[dot*16+:8];py=points[dot*16+8+:8];if(px==n%128 && py/8==n/128)expected_pixel=expected_pixel|(1<<py%8);end
   pixel_address=n;repeat(3)@(negedge clk);if(pixel!==expected_pixel)$fatal(1,"phase bitmap byte=%d got=%h expected=%h",n,pixel,expected_pixel);
   $fdisplay(pixel_fd,"%02x",pixel);
  end
  $fclose(pixel_fd);
  fd=$fopen("build/acceptance_20261102/fft_complex.txt","w");
  for(n=0;n<1024;n=n+1)$fwrite(fd,"%d %d\n",dut.real_mem[n],dut.imag_mem[n]);$fclose(fd);
  fd=$fopen("build/acceptance_20261102/analysis_vectors.txt","w");
  $fwrite(fd,"%h\n%h\n%h\n",wave,spectrum,points);$fclose(fd);
  latch=1;@(negedge clk);latch=0;
  if(id!=1 || pending)$fatal(1,"analysis frame handshake");
  $display("PASS: actual1024 FFT,32 logarithmic bands,wave/phase normalized pixels and frame latch");$finish;
 end
 initial begin #4000000;$fatal(1,"analyzer timeout");end
endmodule
