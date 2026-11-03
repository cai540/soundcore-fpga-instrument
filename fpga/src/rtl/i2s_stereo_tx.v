// Standard Philips/NXP I2S transmitter, 16-bit signed mono duplicated to
// left and right 32-bit slots. No stored audio or software audio path.
//
// Required input: an exact, low-jitter 12.288 MHz clock (256 * 48 kHz).
// Derived clocks: BCLK = 3.072 MHz (64 * 48 kHz), LRCLK = 48 kHz.
// A PLL/clock-source and actual DAC/pin connection are NOT included here.
module i2s_stereo_tx (
    input  wire               clk_audio,
    input  wire               rst_n,
    input  wire signed [15:0] sample_in,
    output reg                sample_tick,
    output reg                i2s_bclk,
    output reg                i2s_lrclk,
    output reg                i2s_sd
);
    reg [1:0]  subcycle;
    reg [5:0]  slot;
    reg [15:0] sample_hold;
    wire [5:0] next_slot = slot + 6'd1;

    always @(posedge clk_audio or negedge rst_n) begin
        if (!rst_n) begin
            subcycle    <= 2'd0;
            slot        <= 6'd63;
            sample_hold <= 16'd0;
            sample_tick <= 1'b0;
            i2s_bclk   <= 1'b0;
            i2s_lrclk  <= 1'b1;
            i2s_sd     <= 1'b0;
        end else begin
            subcycle    <= subcycle + 2'd1;
            sample_tick <= 1'b0;

            if (subcycle == 2'd1)
                i2s_bclk <= 1'b1; // receiver latches current data
            if (subcycle == 2'd3) begin
                i2s_bclk  <= 1'b0; // source prepares next bit
                slot       <= next_slot;
                i2s_lrclk <= next_slot[5];

                // The word-select edge precedes each channel's MSB by one
                // BCLK, so slots 0 and 32 are the required one-bit delay.
                if (next_slot == 6'd0) begin
                    sample_tick <= 1'b1;
                    i2s_sd     <= 1'b0;
                end else if (next_slot == 6'd1) begin
                    // The synth has four clk_audio cycles after sample_tick
                    // to update sample_in before the left MSB is sent.
                    sample_hold <= sample_in;
                    i2s_sd     <= sample_in[15];
                end else if (next_slot >= 6'd2 && next_slot <= 6'd16)
                    i2s_sd <= sample_hold[6'd16 - next_slot];
                else if (next_slot >= 6'd33 && next_slot <= 6'd48)
                    i2s_sd <= sample_hold[6'd48 - next_slot];
                else
                    i2s_sd <= 1'b0;
            end
        end
    end
endmodule
