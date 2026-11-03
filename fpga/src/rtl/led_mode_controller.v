// Single-colour LED effects; no RGB driver or extra FPGA pins required.
module led_mode_controller #(
    parameter integer STEP_CYCLES = 1228800
) (
    input wire clk,
    input wire rst_n,
    input wire [1:0] mode,
    input wire guide_running,
    input wire [6:0] performance_led,
    input wire [6:0] guide_led,
    output reg [6:0] led_out
);
    localparam integer COUNT_BITS = STEP_CYCLES < 2 ? 1 : $clog2(STEP_CYCLES);
    reg [COUNT_BITS-1:0] step_count;
    reg [2:0] chase_index;
    reg [3:0] breath_phase;
    reg [7:0] pwm;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            step_count <= 0;
            chase_index <= 0;
            breath_phase <= 0;
            pwm <= 0;
        end else begin
            pwm <= pwm + 1'b1;
            if (step_count == STEP_CYCLES-1) begin
                step_count <= 0;
                chase_index <= chase_index == 3'd6 ? 3'd0 : chase_index + 3'd1;
                breath_phase <= breath_phase + 1'b1;
            end else step_count <= step_count + 1'b1;
        end
    end
    always @(*) begin
        case (mode)
            // Follow mode must follow physical/phone playing even while the
            // offline guide is running. Guide LEDs belong to mode 1 only.
            2'd0: led_out = performance_led;
            2'd1: led_out = guide_led;
            2'd2: led_out = 7'b1 << chase_index;
            default: led_out = pwm[7:5] <
                       (breath_phase[3] ? (4'd15-breath_phase) : breath_phase) ?
                       7'h7f : 7'h00;
        endcase
    end
endmodule
