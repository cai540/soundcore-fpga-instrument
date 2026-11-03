// One SSD1315 I2C transaction: START, selectable address/write,
// control byte, data/command byte, STOP. 0x78/0x7A are 7-bit 0x3C/0x3D.
// Both lines are open drain. A NACK is reported to the caller for retry.
module oled_i2c_write2 #(
    parameter integer CLK_DIV = 30
) (
    input wire clk,
    input wire rst_n,
    input wire start,
    input wire [7:0] address_write,
    input wire [7:0] control_byte,
    input wire [7:0] payload_byte,
    inout wire scl,
    inout wire sda,
    output wire busy,
    output reg done,
    output reg ack_ok
);
    localparam [3:0] IDLE=0, START=1, BIT_LOW=2, BIT_HIGH=3,
                     ACK_LOW=4, ACK_HIGH=5, ACK_SAMPLE=9, STOP_LOW=6,
                     STOP_HIGH=7, STOP_RELEASE=8;
    localparam integer DIV_BITS = CLK_DIV < 2 ? 1 : $clog2(CLK_DIV);
    reg [3:0] state;
    reg [DIV_BITS-1:0] divider;
    reg scl_low, sda_low;
    reg [7:0] shift_byte, saved_control, saved_payload;
    reg [2:0] bit_index;
    reg [1:0] byte_index;
    wire tick = divider == CLK_DIV - 1;
    assign scl = scl_low ? 1'b0 : 1'bz;
    assign sda = sda_low ? 1'b0 : 1'bz;
    assign busy = state != IDLE;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            divider <= 0;
            scl_low <= 0;
            sda_low <= 0;
            shift_byte <= 0;
            saved_control <= 0;
            saved_payload <= 0;
            bit_index <= 7;
            byte_index <= 0;
            done <= 0;
            ack_ok <= 0;
        end else begin
            done <= 0;
            if (state == IDLE) begin
                divider <= 0;
                scl_low <= 0;
                sda_low <= 0;
                if (start) begin
                    shift_byte <= address_write;
                    saved_control <= control_byte;
                    saved_payload <= payload_byte;
                    bit_index <= 7;
                    byte_index <= 0;
                    ack_ok <= 1;
                    state <= START;
                end
            end else if (tick) begin
                divider <= 0;
                case (state)
                    START: begin
                        // SDA falls while SCL is released high.
                        sda_low <= 1;
                        state <= BIT_LOW;
                    end
                    BIT_LOW: begin
                        scl_low <= 1;
                        sda_low <= ~shift_byte[bit_index];
                        state <= BIT_HIGH;
                    end
                    BIT_HIGH: begin
                        scl_low <= 0;
                        if (bit_index == 0)
                            state <= ACK_LOW;
                        else begin
                            bit_index <= bit_index - 1'b1;
                            state <= BIT_LOW;
                        end
                    end
                    ACK_LOW: begin
                        scl_low <= 1;
                        sda_low <= 0;
                        state <= ACK_HIGH;
                    end
                    ACK_HIGH: begin
                        scl_low <= 0;
                        state <= ACK_SAMPLE;
                    end
                    ACK_SAMPLE: begin
                        // Sample only after SCL has actually risen; this also
                        // gives the slave a full high phase to drive ACK.
                        if (sda != 1'b0) begin
                            ack_ok <= 0;
                            state <= STOP_LOW;
                        end else if (byte_index != 2) begin
                            byte_index <= byte_index + 1'b1;
                            shift_byte <= byte_index == 0 ? saved_control : saved_payload;
                            bit_index <= 7;
                            state <= BIT_LOW;
                        end else
                            state <= STOP_LOW;
                    end
                    STOP_LOW: begin
                        scl_low <= 1;
                        sda_low <= 1;
                        state <= STOP_HIGH;
                    end
                    STOP_HIGH: begin
                        scl_low <= 0;
                        state <= STOP_RELEASE;
                    end
                    STOP_RELEASE: begin
                        sda_low <= 0;
                        done <= 1;
                        state <= IDLE;
                    end
                    default: state <= IDLE;
                endcase
            end else
                divider <= divider + 1'b1;
        end
    end
endmodule
