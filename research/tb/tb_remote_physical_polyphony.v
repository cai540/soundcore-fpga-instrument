`timescale 1ns/1ps
module tb_remote_physical_polyphony;
    reg clk=0, rst_n=0, sample_tick=0;
    reg strike_valid=0, remote_strike_valid=0;
    reg [2:0] strike_channel=0, remote_strike_channel=0, bank=0;
    reg [6:0] pressed=0, remote_pressed=0;
    wire [31:0] gate;
    wire [191:0] note_index;
    wire [255:0] velocity;
    wire [95:0] voice_zone;
    integer i, physical_count, remote_count;
    always #5 clk=~clk;
    strike_voice_allocator32 #(.BANKED_MODE(1),.REMOTE_ENABLE(1),
        .HOLD_SAMPLES(2),.RELEASE_SAMPLES(2)) dut (
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),
        .strike_valid(strike_valid),.strike_channel(strike_channel),
        .strike_velocity(8'd100),.pressed(pressed),
        .remote_strike_valid(remote_strike_valid),
        .remote_strike_channel(remote_strike_channel),
        .remote_strike_velocity(8'd180),.remote_pressed(remote_pressed),
        .level_valid(1'b0),.level_channel(3'd0),.level_velocity(8'd0),
        .bank(bank),.banked_enable(1'b1),.sustain(1'b0),.clear_all(1'b0),
        .gate(gate),.note_index(note_index),.velocity(velocity),
        .voice_zone(voice_zone)
    );
    task tick;
        begin @(negedge clk); sample_tick=1; @(negedge clk); sample_tick=0; end
    endtask
    task hit_physical;
        input [2:0] pad;
        begin
            @(negedge clk); pressed[pad]=1; strike_channel=pad; strike_valid=1;
            @(negedge clk); strike_valid=0; tick();
        end
    endtask
    task hit_remote;
        input [2:0] pad;
        begin
            @(negedge clk); remote_pressed[pad]=1; remote_strike_channel=pad;
            remote_strike_valid=1;
            @(negedge clk); remote_strike_valid=0; tick();
        end
    endtask
    task counts;
        input integer expected_physical, expected_remote;
        begin
            physical_count=0; remote_count=0;
            for(i=0;i<32;i=i+1) if(gate[i]) begin
                if(dut.active_remote[i]) remote_count=remote_count+1;
                else physical_count=physical_count+1;
            end
            if(physical_count!=expected_physical || remote_count!=expected_remote)
                $fatal(1,"owners physical=%0d remote=%0d expected=%0d/%0d",
                    physical_count,remote_count,expected_physical,expected_remote);
        end
    endtask
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        hit_physical(0); hit_remote(0); hit_remote(1);
        counts(1,2);
        @(negedge clk); remote_pressed[0]=0;
        repeat(4) tick();
        counts(1,1);
        @(negedge clk); pressed[0]=0;
        repeat(4) tick();
        counts(0,1);
        hit_remote(1); counts(0,1);
        @(negedge clk); remote_pressed=0;
        repeat(4) tick(); counts(0,0);
        $display("PASS: physical and remote note ownership is isolated");
        $finish;
    end
endmodule
