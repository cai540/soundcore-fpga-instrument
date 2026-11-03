// 16x16 glyphs: upper line left aligned, lower line right aligned.
// Long lines scroll to keep the current syllable visible. Completed pixels
// are inverted from left to right, giving a monochrome KTV progress sweep.
module oled_lyric_columns #(
    parameter FONT_FILE="@FPGA_ROOT@/src/assets/8735f9a1_lyric_font.mem",
    parameter TEXT_FILE="@FPGA_ROOT@/src/assets/a2721c16_lyric_text.mem",
    parameter META_FILE="@FPGA_ROOT@/src/assets/1413871d_lyric_phrases.mem"
)(
    input wire clk,rst_n,
    input wire [6:0] phrase,
    input wire [4:0] character,
    input wire [7:0] progress,
    input wire [1:0] page,
    input wire [6:0] column,
    output wire [7:0] pixels,
    output wire ready
);
    reg [7:0] font[0:16383];
    reg [8:0] text[0:4095];
    reg [15:0] metadata[0:127];
    initial begin $readmemh(FONT_FILE,font);$readmemh(TEXT_FILE,text);$readmemh(META_FILE,metadata);end
    reg [15:0] meta;
    reg [8:0] glyph;
    reg [7:0] font_byte;
    wire row=page[1];
    wire [4:0] length1=meta[4:0],length2=meta[9:5];
    wire [4:0] length=row ? length2:length1;
    wire [5:0] active_index=row ? (character>=length1 ? character-length1:0):character;
    wire [5:0] bounded_index=active_index>=length ? (length==0 ? 0:length-1):active_index;
    wire [4:0] scroll=length>8 && bounded_index>7 ?
        (bounded_index-7>length-8 ? length-8:bounded_index-7):0;
    wire [3:0] margin=row && length<8 ? 8-length:0;
    wire [4:0] local_cell={2'd0,column[6:4]}+scroll-margin;
    wire blank=column[6:4]<margin || local_cell>=length;
    wire [5:0] absolute_character=local_cell+(row ? length1:0);
    wire invert=!blank && (absolute_character<character ||
        (absolute_character==character && (progress==255 || column[3:0]<progress[7:4])));
    always @(posedge clk)begin
        meta<=metadata[phrase];
        glyph<=blank ? 9'd0:text[{phrase,row,local_cell[3:0]}];
        font_byte<=font[{glyph,page[0],column[3:0]}];
    end
    wire [24:0] request={phrase,character,progress[7:4],page,column};
    reg [24:0] last_request;
    reg [2:0] settled;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin last_request<=0;settled<=0;end
        else if(last_request!=request)begin last_request<=request;settled<=0;end
        else if(settled!=7)settled<=settled+1'b1;
    end
    assign ready=settled>=5;
    assign pixels=font_byte ^ (invert ? 8'hff:8'h00);
endmodule
