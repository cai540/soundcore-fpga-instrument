// Two active-low board keys adjust the final speaker gain by one step per press.
module volume_buttons #(
    parameter integer DEBOUNCE_CYCLES = 122880
) (
    input wire clk,
    input wire rst_n,
    input wire key_up_n,
    input wire key_down_n,
    output reg [2:0] gain_level
);
    localparam integer COUNT_BITS = DEBOUNCE_CYCLES < 2 ? 1 :
        $clog2(DEBOUNCE_CYCLES);
    reg [1:0] sync1, sync2, stable;
    reg [COUNT_BITS-1:0] count [0:1];
    wire up_press = stable[0] && !sync2[0] &&
        count[0] == DEBOUNCE_CYCLES - 1;
    wire down_press = stable[1] && !sync2[1] &&
        count[1] == DEBOUNCE_CYCLES - 1;
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync1 <= 2'b11;
            sync2 <= 2'b11;
            stable <= 2'b11;
            count[0] <= {COUNT_BITS{1'b0}};
            count[1] <= {COUNT_BITS{1'b0}};
            gain_level <= 3'd2; // levels: 1x, 2x, 4x, 6x, 8x, 16x
        end else begin
            sync1 <= {key_down_n, key_up_n};
            sync2 <= sync1;
            for (i = 0; i < 2; i = i + 1) begin
                if (sync2[i] == stable[i])
                    count[i] <= {COUNT_BITS{1'b0}};
                else if (count[i] == DEBOUNCE_CYCLES - 1) begin
                    stable[i] <= sync2[i];
                    count[i] <= {COUNT_BITS{1'b0}};
                end else
                    count[i] <= count[i] + 1'b1;
            end
            if (up_press && !down_press && gain_level < 3'd5)
                gain_level <= gain_level + 1'b1;
            else if (down_press && !up_press && gain_level > 3'd0)
                gain_level <= gain_level - 1'b1;
        end
    end
endmodule
