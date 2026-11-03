`timescale 1ns/1ps
module tb_digital_performance_input;
    reg clk = 0;
    always #10 clk = ~clk;
    reg rst_n = 0;
    reg [3:0] sensor_active = 0;
    reg encoder_a = 0, encoder_b = 0;
    wire [3:0] gate;
    wire [7:0] bend;
    digital_performance_input #(.FILTER_CYCLES(3)) dut (
        .clk(clk), .rst_n(rst_n), .sensor_active(sensor_active),
        .encoder_a(encoder_a), .encoder_b(encoder_b),
        .gate(gate), .bend(bend)
    );

    task settle;
        begin repeat (8) @(posedge clk); #1; end
    endtask
    task encoder_state(input [1:0] ab);
        begin {encoder_a, encoder_b} = ab; settle; end
    endtask
    initial begin
        settle;
        rst_n = 1;
        settle;
        if (gate !== 4'b0000 || bend !== 8'd128) $fatal(1, "reset");
        sensor_active = 4'b0001;
        @(posedge clk); #1;
        sensor_active = 4'b0000; // one-cycle glitch must not trigger
        settle;
        if (gate !== 4'b0000) $fatal(1, "glitch reached gate");
        sensor_active = 4'b1011;
        settle;
        if (gate !== 4'b1011) $fatal(1, "independent sensor gates");
        sensor_active = 4'b1001;
        settle;
        if (gate !== 4'b1001) $fatal(1, "independent release");
        encoder_state(2'b01);
        encoder_state(2'b11);
        encoder_state(2'b10);
        encoder_state(2'b00);
        if (bend !== 8'd136) $fatal(1, "forward detent bend=%d", bend);
        encoder_state(2'b10);
        encoder_state(2'b11);
        encoder_state(2'b01);
        encoder_state(2'b00);
        if (bend !== 8'd128) $fatal(1, "reverse detent bend=%d", bend);
        $display("PASS: independent optical gates, glitch rejection, rotary bend");
        $finish;
    end
endmodule
