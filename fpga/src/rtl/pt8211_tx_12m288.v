// PT8211 right-justified stereo, clocked from the current 12.288 MHz PLL.
// 32 BCLKs/frame, eight source clocks/bit: 256 clocks per nominal 48 kHz
// frame, matching the current 32-voice scheduler's existing time budget.
module pt8211_tx_12m288 #(
    parameter integer OUTPUT_SHIFT = 2
) (
    input wire clk_audio,rst_n,
    input wire signed [15:0] sample_in,
    output reg sample_tick,
    output reg audio_bclk,audio_ws,audio_din
);
    reg [1:0] divider;
    reg [4:0] slot;
    reg [15:0] sample_hold;
    wire [4:0] next_slot=slot+5'd1;
    wire signed [15:0] monitor_sample=sample_in >>> OUTPUT_SHIFT;
    always @(posedge clk_audio or negedge rst_n) begin
        if(!rst_n)begin
            divider<=0;slot<=31;sample_hold<=0;sample_tick<=0;
            audio_bclk<=0;audio_ws<=1;audio_din<=0;
        end else begin
            divider<=divider+1'b1;sample_tick<=0;
            if(divider==3)begin
                audio_bclk<=~audio_bclk;
                if(audio_bclk)begin
                    slot<=next_slot;audio_ws<=next_slot[4];
                    if(slot==31)begin
                        sample_hold<=monitor_sample;
                        audio_din<=monitor_sample[15];sample_tick<=1;
                    end else audio_din<=sample_hold[15-next_slot[3:0]];
                end
            end
        end
    end
endmodule
