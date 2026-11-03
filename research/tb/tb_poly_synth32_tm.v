`timescale 1ns/1ps

module tb_poly_synth32_tm;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg [31:0] gate = 32'b0;
    reg [1023:0] phase_step = 1024'b0;
    reg [255:0] velocity = 256'b0;
    reg timbre = 1'b1;
    wire signed [15:0] sample_out;
    wire sample_valid;
    integer cycle = 0;
    integer frames = 0;
    integer valid_frames = 0;
    integer i;
    reg [31:0] phase_before_5;
    reg [31:0] phase_before_6;
    reg [15:0] env_before_5;
    reg [15:0] env_before_6;
    reg saw_nonzero = 0;

    poly_synth32_tm dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .phase_step(phase_step), .velocity(velocity),
        .timbre(timbre), .sample_out(sample_out),
        .sample_valid(sample_valid)
    );

    initial begin
        for (i = 0; i < 32; i = i + 1) begin
            phase_step[i*32 +: 32] = 32'd20000000 + i*32'd700003;
            velocity[i*8 +: 8] = 8'd150;
        end
        repeat (5) @(negedge clk);
        rst_n = 1'b1;
        gate = 32'hffffffff;
        wait (frames == 24);
        repeat (200) @(negedge clk);
        @(negedge clk);
        if (valid_frames != frames || !saw_nonzero)
            $fatal(1, "32-voice mixer did not produce every frame");
        for (i = 0; i < 32; i = i + 1) begin
            if (dut.phase[i] == 0 || dut.envelope[i] == 0)
                $fatal(1, "voice %0d did not maintain independent state", i);
            if (i > 0 && dut.phase[i] == dut.phase[i-1])
                $fatal(1, "adjacent voices share phase at %0d", i);
        end
        phase_before_5 = dut.phase[5];
        phase_before_6 = dut.phase[6];
        env_before_5 = dut.envelope[5];
        env_before_6 = dut.envelope[6];
        gate[5] = 1'b0;
        wait (frames == 30);
        repeat (200) @(negedge clk);
        @(negedge clk);
        if (dut.envelope[5] >= env_before_5)
            $fatal(1, "released voice 5 did not fade");
        if (dut.envelope[6] == 0 ||
            dut.phase[6] == phase_before_6 ||
            dut.phase[5] == phase_before_5)
            $fatal(1, "release of voice 5 disturbed voice 6");
        if (dut.completed_voice_count != 6'd32)
            $fatal(1, "not all 32 voices were serviced in a frame");
        $display("PASS: 32 independent voices, audio frames and isolated release");
        $finish;
    end

    always @(negedge clk) begin
        if (!rst_n) begin
            cycle = 0;
            sample_tick = 1'b0;
        end else begin
            sample_tick = (cycle == 0);
            cycle = (cycle + 1) & 255;
            if (sample_tick)
                frames = frames + 1;
        end
    end

    always @(posedge clk) begin
        if (rst_n && sample_valid) begin
            valid_frames = valid_frames + 1;
            if (sample_out != 0)
                saw_nonzero = 1'b1;
        end
    end

    initial begin
        #5000000;
        $fatal(1, "32-voice test timed out");
    end
endmodule
