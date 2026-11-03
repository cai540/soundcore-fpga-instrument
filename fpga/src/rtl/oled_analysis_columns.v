module oled_analysis_columns #(
 parameter HEADER_FILE="@FPGA_ROOT@/src/assets/dcee7f5f_tools_display_headers.mem"
)(input wire clk,input wire[1:0] mode,input wire[2:0] page,input wire[6:0] column,
 input wire[511:0] wave_data,input wire[255:0] spectrum_data,
 input wire[7:0] phase_pixels,output reg[7:0] pixels);
 reg[7:0] header[0:767];initial $readmemh(HEADER_FILE,header);
 reg[7:0] header_q;
 always @(posedge clk)header_q<=header[(mode-1)*256+{page[0],column}];
 integer bit_index,y;reg[5:0] low_y,high_y;reg[7:0] height;
 always @* begin
  pixels=0;low_y=wave_data[column[6:2]*16 +: 8];high_y=wave_data[column[6:2]*16+8 +: 8];
  height=spectrum_data[column[6:2]*8 +: 8];
  if(page<2)pixels=header_q;
  else if(mode==3)pixels=phase_pixels;
  else for(bit_index=0;bit_index<8;bit_index=bit_index+1)begin
   y=(page-2)*8+bit_index;
   if(mode==1 && y>=low_y && y<=high_y)pixels[bit_index]=1;
   if(mode==2 && column[1:0]!=3 && y>=48-height)pixels[bit_index]=1;
  end
 end
endmodule
