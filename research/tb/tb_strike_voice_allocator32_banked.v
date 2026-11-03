`timescale 1ns/1ps
module tb_strike_voice_allocator32_banked;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg sample_tick = 0;
    reg strike_valid = 0;
    reg [2:0] strike_channel = 0;
    reg [7:0] strike_velocity = 8'd96;
    reg [6:0] pressed = 0;
    reg [2:0] bank = 0;
    reg sustain = 0;
    reg clear_all = 0;
    wire [31:0] gate;
    wire [191:0] note_index;
    wire [255:0] velocity;
    wire [95:0] voice_zone;
    integer n, i, count, found;

    strike_voice_allocator32 #(.BANKED_MODE(1), .HOLD_SAMPLES(2),
                               .RELEASE_SAMPLES(2)) dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .pressed(pressed),
        .level_valid(1'b0), .level_channel(3'd0),
        .level_velocity(8'd0), .bank(bank), .banked_enable(1'b1),
        .sustain(sustain),
        .clear_all(clear_all), .gate(gate), .note_index(note_index),
        .velocity(velocity), .voice_zone(voice_zone)
    );

    task tick_sample;
        begin
            @(negedge clk); sample_tick = 1;
            @(negedge clk); sample_tick = 0;
        end
    endtask
    task hit;
        input [2:0] pad;
        begin
            @(negedge clk);
            pressed[pad] = 1;
            strike_channel = pad;
            strike_valid = 1;
            @(negedge clk); strike_valid = 0;
            tick_sample();
            @(negedge clk); pressed[pad] = 0;
        end
    endtask
    task require_note;
        input [5:0] note;
        begin
            found = 0;
            for (i = 0; i < 32; i = i+1)
                if (gate[i] && note_index[i*6 +: 6] == note)
                    found = 1;
            if (!found) $fatal(1, "missing active note %0d", note);
        end
    endtask

    initial begin
        repeat (3) @(negedge clk); rst_n = 1;
        sustain = 1;
        bank = 0; hit(0);
        bank = 1; hit(0);
        require_note(0);
        require_note(7);

        @(negedge clk); clear_all = 1;
        @(negedge clk); clear_all = 0;
        if (gate !== 0) $fatal(1, "clear_all did not drop every gate");

        // Sequentially play all 32 pitches while sustain retains old notes.
        for (n = 0; n < 32; n = n+1) begin
            bank = n / 7;
            hit(n % 7);
        end
        count = 0;
        for (i = 0; i < 32; i = i+1)
            if (gate[i]) count = count+1;
        if (count != 32) $fatal(1, "expected 32 active notes, got %0d", count);
        for (n = 0; n < 32; n = n+1)
            require_note(n);
        bank = 4;
        for (n = 0; n < 7; n = n+1) begin
            hit(n);
            require_note(28+n);
        end
        count = 0;
        for (i = 0; i < 32; i = i+1)
            if (gate[i]) count = count+1;
        if (count != 32) $fatal(1, "35-note range changed 32-voice capacity");
        // A full 32-slot pool may steal older active voices; the newest three
        // distinct top-bank notes must survive the subsequent requests.
        require_note(32);
        require_note(33);
        require_note(34);

        sustain = 0;
        repeat (4) tick_sample();
        if (gate !== 0) $fatal(1, "sustain-off failed to release notes");
        $display("PASS: five full banks, 35 reachable notes, 32 voices and release");
        $finish;
    end
endmodule
