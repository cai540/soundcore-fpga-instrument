`timescale 1ns/1ps
`include "board/product_song_catalog.vh"
module tb_product_song_guide;
    reg clk=0,rst_n=0,song=0,valid=0;
    reg [1:0] ui=0;
    reg [2:0] bank=0,pad=0;
    wire [10:0] index,length;
    wire [2:0] target_bank,target_pad;
    wire complete,correct,wrong;
    integer s,previous,hits,total_hits=0;
    wire continuation = dut.target_word[22];
    always #5 clk=~clk;
    song_guide_long #(.LENGTH0(`PRODUCT_SONG0_EVENTS),.LENGTH1(`PRODUCT_SONG1_EVENTS),
        .ROM0_FILE(`PRODUCT_SONG0_ROM),.ROM1_FILE(`PRODUCT_SONG1_ROM)) dut(
        .clk(clk),.rst_n(rst_n),.ui_state(ui),.song_select(song),.strike_valid(valid),.strike_bank(bank),.strike_pad(pad),
        .step_index(index),.song_length(length),.target_bank(target_bank),.target_pad(target_pad),
        .completed(complete),.correct_pulse(correct),.wrong_pulse(wrong));
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(s=0;s<2;s=s+1)begin
            ui=1;song=s;valid=0;repeat(3)@(negedge clk);ui=2;hits=0;
            while(!complete)begin
                @(negedge clk);
                if(!complete && target_pad<7 && !continuation)begin
                    previous=index;bank=target_bank;pad=(target_pad+1)%7;valid=1;
                    @(negedge clk);
                    if(index!=previous || !wrong)$fatal(1,"wrong phone/physical pad advanced guide song=%0d step=%0d",s,previous);
                    valid=0;@(negedge clk);pad=target_pad;bank=target_bank;valid=1;
                    @(negedge clk);
                    if(index!=previous+1 || !correct)$fatal(1,"correct target failed song=%0d step=%0d",s,previous);
                    hits=hits+1;valid=0;
                end
            end
            if(index!=length)$fatal(1,"guide did not finish at catalogue length");
            if(s==1 && hits!=`PRODUCT_SONG1_WORDS)$fatal(1,"new song must ask for exactly one strike per lyric word: got=%0d expected=%0d",hits,`PRODUCT_SONG1_WORDS);
            $display("PASS: song %0d guide %0d pitched targets; wrong pad rejected, target bank follows ROM",s,hits);total_hits=total_hits+hits;
        end
        $display("PASS: both product songs completed strict guide (%0d targets)",total_hits);$finish;
    end
    initial begin #10000000;$fatal(1,"guide timeout");end
endmodule
