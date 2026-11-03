// MIDI 60..91 (C4..G6), 32 independent note increments at 48 kHz.
module note_step_table32 (
    input  wire [4:0] note_index,
    output reg  [31:0] phase_step
);
    always @* begin
        case (note_index)
            5'd0: phase_step = 32'd23409859;
            5'd1: phase_step = 32'd24801882;
            5'd2: phase_step = 32'd26276679;
            5'd3: phase_step = 32'd27839171;
            5'd4: phase_step = 32'd29494575;
            5'd5: phase_step = 32'd31248413;
            5'd6: phase_step = 32'd33106541;
            5'd7: phase_step = 32'd35075158;
            5'd8: phase_step = 32'd37160835;
            5'd9: phase_step = 32'd39370534;
            5'd10: phase_step = 32'd41711627;
            5'd11: phase_step = 32'd44191930;
            5'd12: phase_step = 32'd46819719;
            5'd13: phase_step = 32'd49603764;
            5'd14: phase_step = 32'd52553357;
            5'd15: phase_step = 32'd55678342;
            5'd16: phase_step = 32'd58989149;
            5'd17: phase_step = 32'd62496826;
            5'd18: phase_step = 32'd66213081;
            5'd19: phase_step = 32'd70150316;
            5'd20: phase_step = 32'd74321671;
            5'd21: phase_step = 32'd78741067;
            5'd22: phase_step = 32'd83423255;
            5'd23: phase_step = 32'd88383859;
            5'd24: phase_step = 32'd93639437;
            5'd25: phase_step = 32'd99207528;
            5'd26: phase_step = 32'd105106715;
            5'd27: phase_step = 32'd111356685;
            5'd28: phase_step = 32'd117978298;
            5'd29: phase_step = 32'd124993653;
            5'd30: phase_step = 32'd132426162;
            5'd31: phase_step = 32'd140300631;
        endcase
    end
endmodule
