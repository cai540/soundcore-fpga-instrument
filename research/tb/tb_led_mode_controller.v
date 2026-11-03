`timescale 1ns/1ps
module tb_led_mode_controller;
    reg clk=0,rst_n=0,guide_running=0;
    reg [1:0] mode=0;
    wire [6:0] led;
    integer i, saw_on=0,saw_off=0;
    always #5 clk=~clk;
    led_mode_controller #(.STEP_CYCLES(3)) dut (
        .clk(clk),.rst_n(rst_n),.mode(mode),
        .guide_running(guide_running),
        .performance_led(7'b0000101),.guide_led(7'b0100000),
        .led_out(led)
    );
    initial begin
        repeat(2)@(negedge clk);rst_n=1;
        if(led!=7'b0000101)$fatal(1,"follow-key LED wrong");
        guide_running=1;
        #1;if(led!=7'b0000101)$fatal(1,"guide state hijacked follow-key mode");
        mode=1;guide_running=0;
        #1;if(led!=7'b0100000)$fatal(1,"forced guide LED wrong");
        mode=0;
        #1;if(led!=7'b0000101)$fatal(1,"guide-to-follow did not restore key LED");
        mode=2;
        for(i=0;i<25;i=i+1)begin
            @(negedge clk);
            if(led==0 || (led & (led-1))!=0)$fatal(1,"chase not one-hot");
        end
        mode=3;
        for(i=0;i<1500;i=i+1)begin
            @(negedge clk);
            if(led!=0 && led!=7'h7f)
                $fatal(1,"breathing LEDs are not driven identically");
            if(led==0)saw_off=1;
            if(led==7'h7f)saw_on=1;
        end
        if(!saw_on || !saw_off)$fatal(1,"breathing did not modulate");
        $display("PASS: single-colour follow, guide, chase and breathing modes");
        $finish;
    end
endmodule
