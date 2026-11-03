// Two 128x32 Chinese song-selection frames, read one column byte at a time.
// The rest of the OLED remains available for the seven force meters.
module oled_panel_menu_columns (
    input wire clk,
    input wire song,
    input wire [1:0] page,
    input wire [6:0] column,
    output reg [7:0] pixels
);
    reg [7:0] frames [0:1023];
    initial $readmemh("@FPGA_ROOT@/src/assets/3f457cea_panel_menu_frames.mem",frames);
    always @(posedge clk) pixels <= frames[{song,page,column}];
endmodule
