`timescale 1ns/1ps
module tb_song_guide_long;
    reg clk=0,rst_n=0,hit=0;
    reg [1:0] state=0;
    reg [2:0] bank=0,pad=0;
    wire [10:0] step,length;
    wire [2:0] target_bank,target_pad;
    wire [15:0] duration_ms;
    wire completed,correct,wrong;
    wire [6:0] leds;
    always #5 clk=~clk;
    song_guide_long #(.LENGTH0(3),
        .ROM0_FILE("tb/long_song_fixture.mem")) dut (
        .clk(clk),.rst_n(rst_n),.ui_state(state),.song_select(1'b0),
        .strike_valid(hit),.strike_bank(bank),.strike_pad(pad),
        .step_index(step),.song_length(length),
        .target_bank(target_bank),.target_pad(target_pad),
        .target_duration_ms(duration_ms),.completed(completed),
        .correct_pulse(correct),.wrong_pulse(wrong),.target_led(leds)
    );
    task strike;
        input [2:0] b,p;
        begin
            @(negedge clk);bank=b;pad=p;hit=1;
            @(negedge clk);hit=0;
        end
    endtask
    initial begin
        repeat(2)@(negedge clk);rst_n=1;state=2;
        repeat(2)@(negedge clk);
        if(length!=3 || target_bank!=0 || target_pad!=0 ||
           duration_ms!=400 || leds!=7'b0000001)
            $fatal(1,"first long-song target wrong");
        strike(0,0);
        if(step!=1 || target_bank!=1 || target_pad!=0 || duration_ms!=500)
            $fatal(1,"did not advance to second bank");
        strike(0,0);
        if(step!=1)$fatal(1,"wrong bank advanced");
        strike(1,0);
        if(step!=2 || target_bank!=4 || target_pad!=6 || duration_ms!=600)
            $fatal(1,"third target wrong");
        strike(4,6);
        if(!completed || step!=3 || leds!=0)$fatal(1,"completion wrong");
        $display("PASS: long guide checks bank+pad, durations and completion");
        $finish;
    end
endmodule
