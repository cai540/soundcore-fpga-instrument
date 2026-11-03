`timescale 1ns/1ps
module tb_oled_karaoke_render;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg [6:0] phrase=0;
    reg [4:0] character=0;
    reg [7:0] progress=0;
    reg [1:0] page=0;
    reg [6:0] column=0;
    wire [7:0] pixel;
    wire ready;
    integer test_case,p,c,fd;
    reg [1023:0] path;
    oled_lyric_columns dut(.clk(clk),.rst_n(rst_n),.phrase(phrase),.character(character),.progress(progress),
        .page(page),.column(column),.pixels(pixel),.ready(ready));
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(test_case=0;test_case<5;test_case=test_case+1)begin
            case(test_case)
                0:begin phrase=0;character=0;progress=0;end
                1:begin phrase=0;character=0;progress=128;end
                2:begin phrase=0;character=7;progress=128;end
                3:begin phrase=4;character=16;progress=255;end
                4:begin phrase=14;character=5;progress=128;end
            endcase
            $sformat(path,"build/karaoke_oled_%0d.hex",test_case);fd=$fopen(path,"w");
            for(p=0;p<4;p=p+1)for(c=0;c<128;c=c+1)begin
                page=p;column=c;repeat(8)@(negedge clk);
                if(!ready || (^pixel)===1'bx)$fatal(1,"lyric ROM pipeline not settled");
                $fdisplay(fd,"%02x",pixel);
            end
            $fclose(fd);
        end
        $display("PASS: 5 actual RTL lyric frames captured (alignment, half glyph, second line, scrolling, Chilege)");$finish;
    end
endmodule
