`timescale 1ns/1ps

module tb_playable_synth4;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg [3:0] gate = 4'b1111;
    reg [19:0] note_index = {4{5'd31}};
    reg [31:0] velocity = 32'h40_40_40_40;
    reg [7:0] bend = 8'd128;
    reg timbre = 1'b0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    reg [31:0] phase_before;
    reg [31:0] new_step;
    integer active_samples = 0;
    integer other_voice_samples = 0;
    integer i;

    playable_synth4 dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .gate(gate), .note_index(note_index), .velocity(velocity),
        .bend(bend), .timbre(timbre),
        .sample_out(sample_out), .sample_valid(sample_valid)
    );

    task tick;
        begin
            @(negedge clk) sample_tick = 1'b1;
            @(negedge clk) sample_tick = 1'b0;
            repeat (2) @(negedge clk);
        end
    endtask

    initial begin
        #20 rst_n = 1'b1;
        note_index = {5'd11, 5'd7, 5'd4, 5'd0};
        #1;
        if (dut.steps[31:0] !== 32'd23409859 ||
            dut.steps[63:32] !== 32'd29494575 ||
            dut.steps[95:64] !== 32'd35075158 ||
            dut.steps[127:96] !== 32'd44191930)
            $fatal(1, "Four note indices mapped to %0d %0d %0d %0d",
                   dut.steps[31:0], dut.steps[63:32],
                   dut.steps[95:64], dut.steps[127:96]);

        for (i = 0; i < 300; i = i + 1) begin
            tick();
            if (sample_out != 0)
                active_samples = active_samples + 1;
        end
        if (active_samples < 200)
            $fatal(1, "Four voices did not produce audio");

        // Retuning a held note changes its step without retriggering phase.
        phase_before = dut.synth.v0.phase;
        note_index[4:0] = 5'd2; // C4 -> D4
        #1;
        new_step = dut.steps[31:0];
        if (new_step !== 32'd26276679)
            $fatal(1, "Held note did not retune to D4");
        tick();
        if (dut.synth.v0.phase !== phase_before + new_step)
            $fatal(1, "Retuning restarted the held oscillator");

        // Bend changes the increment but must preserve oscillator phase.
        phase_before = dut.synth.v0.phase;
        bend = 8'd200;
        #1;
        new_step = dut.steps[31:0];
        if (new_step <= 32'd26276679)
            $fatal(1, "Positive bend did not raise pitch");
        tick();
        if (dut.synth.v0.phase !== phase_before + new_step)
            $fatal(1, "Pitch bend reset or discontinuously changed phase");

        // Muting one independent voice must not mute the other three.
        gate[0] = 1'b0;
        for (i = 0; i < 300; i = i + 1) begin
            tick();
            if (dut.synth.v1.sample_out != 0)
                other_voice_samples = other_voice_samples + 1;
        end
        if (dut.synth.v0.sample_out !== 16'sd0 ||
            other_voice_samples < 200)
            $fatal(1, "Independent gate/release failed");

        // Out-of-range note cannot keep a voice sounding.
        note_index[4:0] = 5'd31;
        gate[0] = 1'b1;
        #1;
        if (dut.effective_gate[0] !== 1'b0 || dut.steps[31:0] !== 32'd0)
            $fatal(1, "Invalid note was not suppressed");

        // Velocity is independent per voice; zero velocity silences only v0.
        note_index[4:0] = 5'd0;
        velocity[7:0] = 8'd0;
        for (i = 0; i < 100; i = i + 1)
            tick();
        if (dut.synth.v0.sample_out !== 16'sd0)
            $fatal(1, "Zero-velocity voice produced audio");

        $display("PASS: independent note, gate, velocity, retune and live bend");
        $finish;
    end
endmodule
