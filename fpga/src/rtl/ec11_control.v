// Passive EC11: S1, S2 and KEY are active-low switch contacts to GND.
// Each input needs a 3.3 V pull-up (external or verified bank pull-up).
module ec11_control #(
    parameter integer DEBOUNCE_CYCLES = 50000,
    parameter integer LONG_PRESS_CYCLES = 8601600,
    parameter integer LONG_PRESS_ENABLE = 0
) (
    input wire clk,
    input wire rst_n,
    input wire s1_n,
    input wire s2_n,
    input wire key_n,
    output reg enabled,
    output reg [3:0] depth,
    output reg timbre_select
);
    localparam integer COUNT_BITS = DEBOUNCE_CYCLES < 2 ? 1 :
        $clog2(DEBOUNCE_CYCLES);
    reg [2:0] sync1, sync2, stable;
    reg [COUNT_BITS-1:0] count [0:2];
    reg last_s1, last_key;
    localparam integer HOLD_BITS = LONG_PRESS_CYCLES < 2 ? 1 :
        $clog2(LONG_PRESS_CYCLES + 1);
    reg [HOLD_BITS-1:0] hold_count;
    reg long_fired;
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync1 <= 3'b111;
            sync2 <= 3'b111;
            stable <= 3'b111;
            last_s1 <= 1'b1;
            last_key <= 1'b1;
            enabled <= 1'b0;
            depth <= 4'd4;
            timbre_select <= 1'b1;
            hold_count <= {HOLD_BITS{1'b0}};
            long_fired <= 1'b0;
            for (i = 0; i < 3; i = i + 1)
                count[i] <= {COUNT_BITS{1'b0}};
        end else begin
            sync1 <= {key_n, s2_n, s1_n};
            sync2 <= sync1;
            for (i = 0; i < 3; i = i + 1) begin
                if (sync2[i] == stable[i])
                    count[i] <= {COUNT_BITS{1'b0}};
                else if (count[i] == DEBOUNCE_CYCLES - 1) begin
                    stable[i] <= sync2[i];
                    count[i] <= {COUNT_BITS{1'b0}};
                end else
                    count[i] <= count[i] + 1'b1;
            end
            last_s1 <= stable[0];
            last_key <= stable[2];
            if (last_s1 && !stable[0]) begin
                if (stable[1] && depth != 4'd15)
                    depth <= depth + 1'b1;
                else if (!stable[1] && depth != 4'd0)
                    depth <= depth - 1'b1;
            end
            if (!LONG_PRESS_ENABLE && last_key && !stable[2])
                enabled <= ~enabled;
            if (LONG_PRESS_ENABLE && last_key && !stable[2]) begin
                hold_count <= {HOLD_BITS{1'b0}};
                long_fired <= 1'b0;
            end else if (LONG_PRESS_ENABLE && !stable[2] && !long_fired) begin
                if (hold_count == LONG_PRESS_CYCLES - 1) begin
                    timbre_select <= ~timbre_select;
                    long_fired <= 1'b1;
                end else
                    hold_count <= hold_count + 1'b1;
            end
            if (LONG_PRESS_ENABLE && !last_key && stable[2] && !long_fired)
                enabled <= ~enabled;
        end
    end
endmodule
