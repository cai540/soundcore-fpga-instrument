`timescale 1ns/1ps
module tb_strike_voice_allocator;
    reg clk = 0;
    reg rst_n = 0;
    reg sample_tick = 0;
    reg strike_valid = 0;
    reg [2:0] strike_channel = 0;
    reg [7:0] strike_velocity = 0;
    reg [6:0] pressed = 0;
    reg level_valid = 0;
    reg [2:0] level_channel = 0;
    reg [7:0] level_velocity = 0;
    wire [3:0] gate;
    wire [19:0] note_index;
    wire [31:0] velocity;
    integer i;

    always #5 clk = ~clk;
    strike_voice_allocator #(.HOLD_SAMPLES(3)) dut (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .pressed(pressed), .gate(gate),
        .level_valid(level_valid), .level_channel(level_channel),
        .level_velocity(level_velocity),
        .note_index(note_index), .velocity(velocity)
    );
    task strike;
        input [2:0] ch;
        input [7:0] vel;
        begin
            @(negedge clk); strike_channel = ch; strike_velocity = vel;
            strike_valid = 1;
            @(negedge clk); strike_valid = 0;
        end
    endtask
    task tick;
        begin
            @(negedge clk); sample_tick = 1;
            @(negedge clk); sample_tick = 0;
        end
    endtask
    initial begin
        repeat (3) @(negedge clk); rst_n = 1;
        strike(0, 8'd40); strike(1, 8'd70);
        strike(2, 8'd100); strike(3, 8'd130);
        if (gate != 0) $fatal(1, "pending voices must start on sample boundary");
        tick();
        if (gate != 4'hf || note_index !== {5'd7,5'd4,5'd2,5'd0} ||
            velocity !== {8'd130,8'd100,8'd70,8'd40})
            $fatal(1, "four independent strikes did not allocate four voices");

        // Keep all four pads held while repeatedly tapping zone 2. Its own
        // voice may retrigger, but none of the other three may be stolen.
        pressed = 7'b0001111;
        for (i = 0; i < 8; i = i + 1) begin
            strike(2, 8'd100);
            if (gate[3] !== 1'b1 || gate[1:0] !== 2'b11 ||
                dut.pending !== 4'b0100)
                $fatal(1, "retrigger stole an unrelated held voice");
            tick();
            if (gate !== 4'hf ||
                note_index !== {5'd7,5'd4,5'd2,5'd0} ||
                dut.next_voice !== 2'd0)
                $fatal(1, "retrigger changed four held note mappings");
        end

        // Releasing one pad must leave the other three held voices active.
        pressed[2] = 1'b0;
        repeat (3) tick();
        if (gate !== 4'b1011)
            $fatal(1, "release of zone 2 silenced another held voice");
        pressed[2] = 1'b1;
        strike(2, 8'd110);
        tick();
        if (gate !== 4'hf ||
            note_index !== {5'd7,5'd4,5'd2,5'd0})
            $fatal(1, "repress did not restore its original voice");

        strike(7, 8'd200);
        if (gate != 4'hf || dut.next_voice != 2'd0)
            $fatal(1, "slider channel entered voice allocator");
        strike(6, 8'd200);
        if (gate[0] !== 1'b0 || gate[3:1] !== 3'b111)
            $fatal(1, "voice steal failed to make a gate-low interval");
        tick();
        if (gate[0] !== 1'b1 || note_index[4:0] !== 5'd14 ||
            velocity[7:0] !== 8'd200)
            $fatal(1, "fifth strike did not select seventh handpan note");
        pressed = 7'b0;
        for (i = 0; i < 4; i = i + 1) tick();
        if (gate != 0) $fatal(1, "short note holds did not expire");

        pressed[4] = 1'b1;
        strike(4, 8'd90);
        tick();
        for (i = 0; i < 6; i = i + 1) tick();
        if (gate !== 4'b0001 || dut.active_channel[0] !== 3'd4)
            $fatal(1, "held pressure must sustain after minimum tap time");
        @(negedge clk); level_channel = 4; level_velocity = 8'd210; level_valid = 1;
        @(negedge clk); level_valid = 0;
        if (velocity[7:0] !== 8'd210)
            $fatal(1, "held pressure must update the active voice level");
        @(negedge clk); level_velocity = 8'd35; level_valid = 1;
        @(negedge clk); level_valid = 0;
        if (velocity[7:0] !== 8'd210)
            $fatal(1, "fast hard hit must not become soft on rebound");
        pressed[4] = 1'b0;
        #1;
        if (gate[0] !== 1'b0)
            $fatal(1, "release must lower the voice gate");
        if (velocity[7:0] !== 8'd210)
            $fatal(1, "release must preserve level for a natural fade");
        tick(); // retire the old pad-to-voice mapping
        pressed[4] = 1'b1;
        #1;
        if (gate[0] !== 1'b0)
            $fatal(1, "new press must not revive a released old voice");
        strike(4, 8'd110);
        tick();
        if (gate !== 4'b0001 || dut.active_channel[0] !== 3'd4)
            $fatal(1, "repeat strike must use only one allocated voice");
        $display("PASS: zone notes, four voices, held sustain and release gate");
        $finish;
    end
endmodule
