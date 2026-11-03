// One indicator per pressure pad. A strike remains visible briefly even if
// the finger is released before the next visual frame; a held pad stays lit.
module pad_led_feedback #(
    parameter integer FLASH_CYCLES = 1228800
) (
    input wire clk,
    input wire rst_n,
    input wire [6:0] pressed,
    input wire strike_valid,
    input wire [2:0] strike_channel,
    output wire [6:0] led_on
);
    localparam integer TIMER_BITS = FLASH_CYCLES < 2 ? 1 :
                                    $clog2(FLASH_CYCLES + 1);
    reg [TIMER_BITS-1:0] flash_left [0:6];
    genvar pad;
    generate for (pad = 0; pad < 7; pad = pad + 1) begin: each_pad
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n)
                flash_left[pad] <= {TIMER_BITS{1'b0}};
            else if (strike_valid && strike_channel == pad)
                flash_left[pad] <= FLASH_CYCLES;
            else if (flash_left[pad] != 0)
                flash_left[pad] <= flash_left[pad] - 1'b1;
        end
        assign led_on[pad] = pressed[pad] || (flash_left[pad] != 0);
    end endgenerate
endmodule
