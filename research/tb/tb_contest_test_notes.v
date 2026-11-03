`timescale 1ns/1ps

module tb_contest_test_notes;
    reg test_enable = 1'b0;
    reg [3:0] voice_mask = 4'b1111;
    wire [3:0] gate;
    wire [19:0] note_index;
    wire [31:0] velocity;
    wire [7:0] bend;
    wire timbre;
    wire [31:0] f0, f1, f2, f3;

    contest_test_notes dut (
        .test_enable(test_enable), .voice_mask(voice_mask),
        .gate(gate), .note_index(note_index),
        .velocity(velocity), .bend(bend), .timbre(timbre)
    );
    note_step_table n0 (note_index[4:0], f0);
    note_step_table n1 (note_index[9:5], f1);
    note_step_table n2 (note_index[14:10], f2);
    note_step_table n3 (note_index[19:15], f3);

    initial begin
        #1;
        if (gate !== 4'b0000 || velocity !== 32'd0)
            $fatal(1, "Disabled test mode must not produce voice gates");
        test_enable = 1'b1;
        #1;
        if (gate !== 4'b1111 ||
            note_index !== {5'd11, 5'd7, 5'd4, 5'd0} ||
            velocity !== 32'h40_40_40_40 ||
            bend !== 8'd128 || timbre !== 1'b1)
            $fatal(1, "Four-frequency controls are incorrect");
        if (f0 !== 32'd23409859 || f1 !== 32'd29494575 ||
            f2 !== 32'd35075158 || f3 !== 32'd44191930)
            $fatal(1, "Test-mode notes do not map to C4/E4/G4/B4");
        voice_mask = 4'b0101;
        #1;
        if (gate !== 4'b0101)
            $fatal(1, "Individual test voice mask failed");
        test_enable = 1'b0;
        #1;
        if (gate !== 4'b0000)
            $fatal(1, "Test-mode disable failed");
        $display("PASS: contest four-frequency test controls");
        $finish;
    end
endmodule
