// MIDI 60..94 (C4..Bb6), 35 distinct chromatic pitches at 48 kHz.
// phase_step = round(440 * 2^((MIDI-69)/12) * 2^32 / 48000).
module note_step_table35 (
    input wire [5:0] note_index,
    output reg [31:0] phase_step
);
    always @* begin
        case (note_index)
            6'd0: phase_step = 32'd23409859;
            6'd1: phase_step = 32'd24801882;
            6'd2: phase_step = 32'd26276679;
            6'd3: phase_step = 32'd27839171;
            6'd4: phase_step = 32'd29494575;
            6'd5: phase_step = 32'd31248413;
            6'd6: phase_step = 32'd33106541;
            6'd7: phase_step = 32'd35075158;
            6'd8: phase_step = 32'd37160835;
            6'd9: phase_step = 32'd39370534;
            6'd10: phase_step = 32'd41711627;
            6'd11: phase_step = 32'd44191930;
            6'd12: phase_step = 32'd46819719;
            6'd13: phase_step = 32'd49603764;
            6'd14: phase_step = 32'd52553357;
            6'd15: phase_step = 32'd55678342;
            6'd16: phase_step = 32'd58989149;
            6'd17: phase_step = 32'd62496826;
            6'd18: phase_step = 32'd66213081;
            6'd19: phase_step = 32'd70150316;
            6'd20: phase_step = 32'd74321671;
            6'd21: phase_step = 32'd78741067;
            6'd22: phase_step = 32'd83423255;
            6'd23: phase_step = 32'd88383859;
            6'd24: phase_step = 32'd93639437;
            6'd25: phase_step = 32'd99207528;
            6'd26: phase_step = 32'd105106715;
            6'd27: phase_step = 32'd111356685;
            6'd28: phase_step = 32'd117978298;
            6'd29: phase_step = 32'd124993653;
            6'd30: phase_step = 32'd132426162;
            6'd31: phase_step = 32'd140300631;
            6'd32: phase_step = 32'd148643341;
            6'd33: phase_step = 32'd157482134;
            6'd34: phase_step = 32'd166846509;
            default: phase_step = 32'd0;
        endcase
    end
endmodule
