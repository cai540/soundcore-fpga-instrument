`timescale 1ns/1ps

module tb_note_step_table;
    reg [4:0] note_index = 5'd31;
    wire [31:0] phase_step;

    note_step_table dut (.note_index(note_index), .phase_step(phase_step));

    task check;
        input [4:0] index;
        input [31:0] expected;
        begin
            note_index = index;
            #1;
            if (phase_step !== expected)
                $fatal(1, "Note %0d: expected %0d, got %0d",
                       index, expected, phase_step);
        end
    endtask

    initial begin
        check(5'd0, 32'd23409859);  // C4
        check(5'd9, 32'd39370534);  // A4
        check(5'd12, 32'd46819719); // C5
        check(5'd23, 32'd88383859); // B5
        check(5'd24, 32'd0);
        check(5'd31, 32'd0);
        $display("PASS: note table C4-B5 and invalid indices");
        $finish;
    end
endmodule
