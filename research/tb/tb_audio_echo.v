`timescale 1ns/1ps

module tb_audio_echo;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_valid = 1'b0;
    reg echo_enable = 1'b0;
    reg signed [15:0] sample_in = 16'sd0;
    wire signed [15:0] sample_out;
    reg signed [15:0] history [0:3];
    integer count = 0;
    integer i;
    integer expected;
    integer previous;

    audio_echo #(.DEPTH(4)) dut (
        .clk(clk), .rst_n(rst_n), .sample_valid(sample_valid),
        .echo_enable(echo_enable), .sample_in(sample_in),
        .sample_out(sample_out)
    );

    task send_sample;
        input integer value;
        input integer enabled;
        begin
            previous = count >= 4 ? history[count % 4] : 0;
            expected = enabled != 0 ? value + (previous >>> 1) : value;
            if (expected > 32767) expected = 32767;
            if (expected < -32768) expected = -32768;
            history[count % 4] = value;
            count = count + 1;

            @(negedge clk);
            sample_in = value;
            echo_enable = enabled != 0;
            sample_valid = 1'b1;
            @(negedge clk);
            sample_valid = 1'b0;
            @(posedge clk);
            #1;
            if (sample_out !== expected)
                $fatal(1, "Echo sample %0d: expected %0d, got %0d",
                       count, expected, sample_out);
        end
    endtask

    initial begin
        for (i = 0; i < 4; i = i + 1)
            history[i] = 0;
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        send_sample(1000, 1); // unfilled delay must be silent
        send_sample(-3000, 1);
        send_sample(32767, 0); // dry bypass while filling memory
        send_sample(-32768, 1);
        send_sample(2000, 1); // 2000 + 1000/2
        send_sample(-1000, 1); // -1000 + (-3000)/2
        send_sample(32767, 1); // saturates positive
        send_sample(-32768, 1); // saturates negative
        send_sample(1234, 0); // pure dry output
        send_sample(4321, 1); // echo re-enabled, history kept
        $display("PASS: FPGA echo delay, bypass, signed mix and saturation");
        $finish;
    end
endmodule
