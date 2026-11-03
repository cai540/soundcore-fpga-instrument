`timescale 1ns/1ps

module tb_strike_voice_allocator32;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst_n = 1'b0;
    reg sample_tick = 1'b0;
    reg strike_valid = 1'b0;
    reg [2:0] strike_channel = 3'd0;
    reg [7:0] strike_velocity = 8'd120;
    reg level_valid = 1'b0;
    reg [2:0] level_channel = 3'd0;
    reg [7:0] level_velocity = 8'd0;
    reg [6:0] pressed = 7'b0;
    wire [31:0] gate;
    wire [191:0] note_index;
    wire [255:0] velocity;
    wire [95:0] voice_zone;
    integer k;

    strike_voice_allocator32 #(.HOLD_SAMPLES(2),
                               .RELEASE_SAMPLES(1000)) dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity),
        .level_valid(level_valid), .level_channel(level_channel),
        .level_velocity(level_velocity), .pressed(pressed),
        .gate(gate), .note_index(note_index),
        .velocity(velocity), .voice_zone(voice_zone)
    );

    task tap;
        input [2:0] channel;
        input [4:0] expected_slot;
        begin
            @(negedge clk);
            strike_channel = channel;
            if (dut.chosen_voice != expected_slot)
                $fatal(1, "expected slot %0d got %0d", expected_slot,
                       dut.chosen_voice);
            strike_valid = 1'b1;
            @(negedge clk);
            strike_valid = 1'b0;
            sample_tick = 1'b1;
            @(negedge clk);
            sample_tick = 1'b0;
            if (velocity[expected_slot*8 +: 8] != strike_velocity)
                $fatal(1, "slot %0d velocity lost", expected_slot);
        end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst_n = 1'b1;
        pressed[0] = 1'b1;
        tap(3'd0, 5'd0);
        if (!gate[0])
            $fatal(1, "held zone zero did not sound");
        tap(3'd1, 5'd1);
        if (!gate[0] || !gate[1])
            $fatal(1, "new note cut an unrelated held note");
        pressed[0] = 1'b0;
        for (k = 2; k < 32; k = k + 1)
            tap(k % 7, k);
        if (dut.next_voice != 5'd0)
            $fatal(1, "not all 32 slots were allocated");
        for (k = 0; k < 32; k = k + 1)
            if (dut.cooldown[k] == 0 && !dut.voice_valid[k])
                $fatal(1, "slot %0d was reused before release tail", k);
        $display("PASS: 32 pad-triggered voice slots and held-note isolation");
        $finish;
    end
endmodule
