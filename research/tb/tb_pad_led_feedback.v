`timescale 1ns/1ps
module tb_pad_led_feedback;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg [6:0] pressed = 0;
    reg strike_valid = 0;
    reg [2:0] strike_channel = 0;
    wire [6:0] led_on;
    pad_led_feedback #(.FLASH_CYCLES(4)) dut (
        .clk(clk), .rst_n(rst_n), .pressed(pressed),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .led_on(led_on)
    );
    initial begin
        repeat (2) @(negedge clk);
        rst_n = 1;
        pressed = 7'b0000100;
        #1;
        if (led_on !== 7'b0000100) $fatal(1, "AI2 hold mapping");
        strike_channel = 3'd5;
        strike_valid = 1;
        @(negedge clk);
        strike_valid = 0;
        #1;
        if (led_on !== 7'b0100100) $fatal(1, "AI5 strike mapping");
        pressed = 7'b0000000;
        #1;
        if (led_on !== 7'b0100000) $fatal(1, "AI2 release");
        repeat (4) @(negedge clk);
        #1;
        if (led_on !== 7'b0000000) $fatal(1, "flash timeout");
        pressed = 7'b1000001;
        #1;
        if (led_on !== 7'b1000001) $fatal(1, "AI0/AI6 simultaneous");
        $display("PASS: seven independent pad LEDs, hold and short strike");
        $finish;
    end
endmodule
