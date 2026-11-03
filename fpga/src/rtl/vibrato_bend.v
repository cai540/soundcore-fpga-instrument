// FPGA-generated ~5 Hz triangular vibrato at the 48 kHz audio sample tick.
// Maximum depth is ~30 bend codes, around a quarter semitone in this synth.
module vibrato_bend (
    input wire clk,
    input wire rst_n,
    input wire sample_tick,
    input wire enabled,
    input wire [3:0] depth,
    output wire signed [7:0] offset
);
    reg [23:0] phase;
    wire [7:0] p = phase[23:16];
    reg signed [8:0] triangle;
    wire signed [13:0] product = triangle * $signed({1'b0, depth});
    wire signed [13:0] scaled = product >>> 6;
    always @* begin
        case (p[7:6])
            2'b00: triangle = $signed({2'b00, p[5:0], 1'b0});
            2'b01: triangle = 9'sd128 - $signed({2'b00, p[5:0], 1'b0});
            2'b10: triangle = -$signed({2'b00, p[5:0], 1'b0});
            default: triangle = -9'sd128 + $signed({2'b00, p[5:0], 1'b0});
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            phase <= 24'd0;
        else if (sample_tick)
            phase <= phase + 24'd1748;
    end
    assign offset = enabled ? scaled[7:0] : 8'sd0;
endmodule
