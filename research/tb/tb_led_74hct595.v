`timescale 1ns/1ps
module tb_led_74hct595;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg [6:0] led_on = 0;
    wire ser, srclk, rclk;
    reg [7:0] shifted = 0;
    reg [7:0] outputs = 0;
    integer latches = 0;
    led_74hct595 dut (.clk(clk), .rst_n(rst_n), .led_on(led_on),
                      .ser(ser), .srclk(srclk), .rclk(rclk));
    always @(posedge srclk) shifted <= {shifted[6:0], ser};
    always @(posedge rclk) begin
        outputs <= shifted;
        latches = latches + 1;
    end
    initial begin
        repeat (2) @(negedge clk);
        rst_n = 1;
        repeat (30) @(negedge clk);
        if (latches != 1 || outputs !== 8'h00)
            $fatal(1, "initial all-off frame");
        led_on = 7'b1000101;
        repeat (30) @(negedge clk);
        if (latches != 2 || outputs !== 8'b01000101)
            $fatal(1, "AI0 AI2 AI6 mapping");
        led_on = 7'b0000010;
        repeat (30) @(negedge clk);
        if (latches != 3 || outputs !== 8'b00000010)
            $fatal(1, "AI1 updates without stale LEDs");
        repeat (30) @(negedge clk);
        if (latches != 3) $fatal(1, "unchanged status retransmitted");
        $display("PASS: 74HCT595 seven-LED serial mapping and latching");
        $finish;
    end
endmodule
