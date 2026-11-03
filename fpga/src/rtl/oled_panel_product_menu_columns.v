// Native song/mode menu: four song frames and two cursor frames in a 4 KiB ROM.
module oled_panel_product_menu_columns(
    input wire clk,song,demo_mode,mode_menu,mode_cursor,
    input wire [1:0] page,
    input wire [6:0] column,
    output reg [7:0] pixels
);
    wire [2:0] frame=mode_menu ? {2'b10,mode_cursor}:{1'b0,demo_mode,song};
    reg [7:0] frames[0:4095];
    initial $readmemh("@FPGA_ROOT@/src/assets/5862df2a_panel_product_menu_frames.mem",frames);
    always @(posedge clk)pixels<=frames[{frame,page,column}];
endmodule
