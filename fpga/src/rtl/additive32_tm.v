// One playable note, 32 separately phased and enveloped additive components.
// Two clocks per component: 64 of 256 available clocks at 48 kHz.
module additive32_tm (
    input wire clk,
    input wire rst_n,
    input wire sample_tick,
    input wire gate,
    input wire [31:0] base_step,
    input wire [7:0] velocity,
    input wire [31:0] component_mask,
    output reg signed [15:0] sample_out,
    output reg sample_valid
);
    localparam [1:0] OFF=2'd0, ATTACK=2'd1, DECAY=2'd2, SUSTAIN=2'd3;
    reg [31:0] phase [0:31];
    reg [15:0] envelope [0:31];
    reg [1:0] state [0:31];
    reg gate_last [0:31];
    reg busy, mix_stage;
    reg [4:0] slot;
    reg signed [31:0] accumulator;
    reg signed [15:0] wave_reg;
    reg [15:0] amp_reg;
    integer i;
    function signed [15:0] quarter;
        input [5:0] idx;
        begin
            case (idx)
            6'd0: quarter = 16'sd0;
            6'd1: quarter = 16'sd804;
            6'd2: quarter = 16'sd1608;
            6'd3: quarter = 16'sd2410;
            6'd4: quarter = 16'sd3212;
            6'd5: quarter = 16'sd4011;
            6'd6: quarter = 16'sd4808;
            6'd7: quarter = 16'sd5602;
            6'd8: quarter = 16'sd6393;
            6'd9: quarter = 16'sd7179;
            6'd10: quarter = 16'sd7962;
            6'd11: quarter = 16'sd8739;
            6'd12: quarter = 16'sd9512;
            6'd13: quarter = 16'sd10278;
            6'd14: quarter = 16'sd11039;
            6'd15: quarter = 16'sd11793;
            6'd16: quarter = 16'sd12539;
            6'd17: quarter = 16'sd13279;
            6'd18: quarter = 16'sd14010;
            6'd19: quarter = 16'sd14732;
            6'd20: quarter = 16'sd15446;
            6'd21: quarter = 16'sd16151;
            6'd22: quarter = 16'sd16846;
            6'd23: quarter = 16'sd17530;
            6'd24: quarter = 16'sd18204;
            6'd25: quarter = 16'sd18868;
            6'd26: quarter = 16'sd19519;
            6'd27: quarter = 16'sd20159;
            6'd28: quarter = 16'sd20787;
            6'd29: quarter = 16'sd21403;
            6'd30: quarter = 16'sd22005;
            6'd31: quarter = 16'sd22594;
            6'd32: quarter = 16'sd23170;
            6'd33: quarter = 16'sd23731;
            6'd34: quarter = 16'sd24279;
            6'd35: quarter = 16'sd24811;
            6'd36: quarter = 16'sd25329;
            6'd37: quarter = 16'sd25832;
            6'd38: quarter = 16'sd26319;
            6'd39: quarter = 16'sd26790;
            6'd40: quarter = 16'sd27245;
            6'd41: quarter = 16'sd27683;
            6'd42: quarter = 16'sd28105;
            6'd43: quarter = 16'sd28510;
            6'd44: quarter = 16'sd28898;
            6'd45: quarter = 16'sd29268;
            6'd46: quarter = 16'sd29621;
            6'd47: quarter = 16'sd29956;
            6'd48: quarter = 16'sd30273;
            6'd49: quarter = 16'sd30571;
            6'd50: quarter = 16'sd30852;
            6'd51: quarter = 16'sd31113;
            6'd52: quarter = 16'sd31356;
            6'd53: quarter = 16'sd31580;
            6'd54: quarter = 16'sd31785;
            6'd55: quarter = 16'sd31971;
            6'd56: quarter = 16'sd32137;
            6'd57: quarter = 16'sd32285;
            6'd58: quarter = 16'sd32412;
            6'd59: quarter = 16'sd32521;
            6'd60: quarter = 16'sd32609;
            6'd61: quarter = 16'sd32678;
            6'd62: quarter = 16'sd32728;
            6'd63: quarter = 16'sd32757;
            endcase
        end
    endfunction
    function signed [15:0] sine256;
        input [7:0] idx;
        begin
            case (idx[7:6])
                2'd0: sine256 = quarter(idx[5:0]);
                2'd1: sine256 = quarter(6'd63-idx[5:0]);
                2'd2: sine256 = -quarter(idx[5:0]);
                default: sine256 = -quarter(6'd63-idx[5:0]);
            endcase
        end
    endfunction
    function [7:0] weight;
        input [4:0] idx;
        begin
            case (idx)
            5'd0: weight = 8'd32;
            5'd1: weight = 8'd32;
            5'd2: weight = 8'd21;
            5'd3: weight = 8'd16;
            5'd4: weight = 8'd13;
            5'd5: weight = 8'd11;
            5'd6: weight = 8'd9;
            5'd7: weight = 8'd8;
            5'd8: weight = 8'd7;
            5'd9: weight = 8'd6;
            5'd10: weight = 8'd6;
            5'd11: weight = 8'd5;
            5'd12: weight = 8'd5;
            5'd13: weight = 8'd5;
            5'd14: weight = 8'd4;
            5'd15: weight = 8'd4;
            5'd16: weight = 8'd4;
            5'd17: weight = 8'd4;
            5'd18: weight = 8'd3;
            5'd19: weight = 8'd3;
            5'd20: weight = 8'd3;
            5'd21: weight = 8'd3;
            5'd22: weight = 8'd3;
            5'd23: weight = 8'd3;
            5'd24: weight = 8'd3;
            5'd25: weight = 8'd2;
            5'd26: weight = 8'd2;
            5'd27: weight = 8'd2;
            5'd28: weight = 8'd2;
            5'd29: weight = 8'd2;
            5'd30: weight = 8'd2;
            5'd31: weight = 8'd2;
            endcase
        end
    endfunction
    wire component_gate = gate && component_mask[slot];
    wire [5:0] harmonic = {1'b0,slot}+6'd1;
    wire [37:0] harmonic_product = base_step * harmonic;
    wire [31:0] step = harmonic_product[31:0];
    reg [31:0] phase_next;
    reg [15:0] envelope_next;
    reg [1:0] state_next;
    wire [15:0] sustain_target = 16'd44000 - ({11'd0,slot} << 8);
    wire [15:0] attack_step = 16'd4096;
    wire [15:0] decay_step = 16'd96 + ({11'd0,slot} << 3);
    wire [15:0] release_step =
        (envelope[slot] >> 7) >= 8 ? (envelope[slot] >> 7) : 16'd8;
    reg signed [23:0] weighted_wave;
    wire signed [31:0] component_product =
        $signed(wave_reg) * $signed({1'b0,amp_reg});
    wire signed [31:0] sum_next =
        accumulator + (component_product >>> 16);
    always @* begin
        phase_next = phase[slot];
        envelope_next = envelope[slot];
        state_next = state[slot];
        if (!component_mask[slot]) begin
            envelope_next = 16'd0;
            state_next = OFF;
        end else if (component_gate && !gate_last[slot]) begin
            phase_next = 32'd0;
            envelope_next = attack_step;
            state_next = ATTACK;
        end else if (!component_gate) begin
            if (envelope[slot] <= release_step) begin
                envelope_next = 16'd0;
                state_next = OFF;
            end else
                envelope_next = envelope[slot] - release_step;
            if (state[slot] != OFF)
                phase_next = phase[slot] + step;
        end else begin
            phase_next = phase[slot] + step;
            case (state[slot])
                OFF, ATTACK: begin
                    if (envelope[slot] >= 16'hffff-attack_step) begin
                        envelope_next = 16'hffff;
                        state_next = DECAY;
                    end else begin
                        envelope_next = envelope[slot]+attack_step;
                        state_next = ATTACK;
                    end
                end
                DECAY: begin
                    if (envelope[slot] <= sustain_target+decay_step) begin
                        envelope_next = sustain_target;
                        state_next = SUSTAIN;
                    end else
                        envelope_next = envelope[slot]-decay_step;
                end
                SUSTAIN: envelope_next = sustain_target;
                default: begin
                    envelope_next = 16'd0;
                    state_next = OFF;
                end
            endcase
        end
        weighted_wave =
            $signed(sine256(phase_next[31:24])) *
            $signed({1'b0,weight(slot)});
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            mix_stage <= 1'b0;
            slot <= 5'd0;
            accumulator <= 32'sd0;
            wave_reg <= 16'sd0;
            amp_reg <= 16'd0;
            sample_out <= 16'sd0;
            sample_valid <= 1'b0;
            for (i=0; i<32; i=i+1) begin
                phase[i] <= 32'd0;
                envelope[i] <= 16'd0;
                state[i] <= OFF;
                gate_last[i] <= 1'b0;
            end
        end else begin
            sample_valid <= 1'b0;
            if (sample_tick) begin
                busy <= 1'b1;
                mix_stage <= 1'b0;
                slot <= 5'd0;
                accumulator <= 32'sd0;
            end else if (busy && !mix_stage) begin
                phase[slot] <= phase_next;
                envelope[slot] <= envelope_next;
                state[slot] <= state_next;
                gate_last[slot] <= component_gate;
                wave_reg <= weighted_wave >>> 8;
                amp_reg <= envelope_next[15:8] * velocity;
                mix_stage <= 1'b1;
            end else if (busy) begin
                accumulator <= sum_next;
                if (slot == 5'd31) begin
                    busy <= 1'b0;
                    sample_valid <= 1'b1;
                    if (sum_next > 32'sd32767)
                        sample_out <= 16'sh7fff;
                    else if (sum_next < -32'sd32768)
                        sample_out <= 16'sh8000;
                    else
                        sample_out <= sum_next[15:0];
                end else begin
                    slot <= slot + 5'd1;
                    mix_stage <= 1'b0;
                end
            end
        end
    end
endmodule
