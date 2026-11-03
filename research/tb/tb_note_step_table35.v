`timescale 1ns/1ps
module tb_note_step_table35;
    reg [5:0] note_index = 0;
    wire [31:0] phase_step;
    wire [31:0] old_step;
    integer n;
    note_step_table35 dut (.note_index(note_index), .phase_step(phase_step));
    note_step_table32 old_table (
        .note_index(note_index[4:0]), .phase_step(old_step)
    );
    initial begin
        for (n = 0; n < 35; n = n+1) begin
            note_index = n;
            #1;
            if (phase_step == 0)
                $fatal(1, "note %0d has no frequency", n);
            if (n < 32 && phase_step !== old_step)
                $fatal(1, "old note %0d changed", n);
            if (n > 0 && phase_step <= old_step && n == 32)
                $fatal(1, "note 32 is not above note 31");
        end
        note_index = 6'd32; #1;
        if (phase_step !== 32'd148643341) $fatal(1,"bad note 32");
        note_index = 6'd33; #1;
        if (phase_step !== 32'd157482134) $fatal(1,"bad note 33");
        note_index = 6'd34; #1;
        if (phase_step !== 32'd166846509) $fatal(1,"bad note 34");
        note_index = 6'd35; #1;
        if (phase_step !== 0) $fatal(1,"invalid note sounded");
        $display("PASS: 35 note steps, legacy 0..31 unchanged, invalid note silent");
        $finish;
    end
endmodule
