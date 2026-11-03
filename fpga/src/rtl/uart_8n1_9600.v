// JDY-23 transparent UART. At 12.288 MHz, 1280 clocks/bit = 9600 baud.
module uart_8n1_9600 #(
    parameter integer CLKS_PER_BIT = 1280
) (
    input wire clk,
    input wire rst_n,
    input wire rx,
    output reg rx_valid,
    output reg [7:0] rx_byte,
    output reg tx,
    input wire tx_valid,
    input wire [7:0] tx_byte,
    output wire tx_ready
);
    localparam integer COUNT_BITS = CLKS_PER_BIT < 2 ? 1 :
                                    $clog2(CLKS_PER_BIT+1);
    reg rx_meta,rx_sync;
    reg [1:0] rx_state,tx_state;
    reg [COUNT_BITS-1:0] rx_count,tx_count;
    reg [2:0] rx_bit,tx_bit;
    reg [7:0] rx_shift,tx_shift;
    assign tx_ready=tx_state==0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_meta<=1; rx_sync<=1;
            rx_state<=0; rx_count<=0; rx_bit<=0;
            rx_shift<=0; rx_valid<=0; rx_byte<=0;
            tx_state<=0; tx_count<=0; tx_bit<=0;
            tx_shift<=0; tx<=1;
        end else begin
            rx_meta<=rx;
            rx_sync<=rx_meta;
            rx_valid<=0;
            case (rx_state)
                0: if (!rx_sync) begin
                    rx_state<=1;
                    rx_count<=CLKS_PER_BIT/2;
                end
                1: if (rx_count==0) begin
                    if (!rx_sync) begin
                        rx_state<=2;
                        rx_count<=CLKS_PER_BIT-1;
                        rx_bit<=0;
                    end else rx_state<=0;
                end else rx_count<=rx_count-1'b1;
                2: if (rx_count==0) begin
                    rx_shift[rx_bit]<=rx_sync;
                    rx_count<=CLKS_PER_BIT-1;
                    if (rx_bit==7) rx_state<=3;
                    else rx_bit<=rx_bit+1'b1;
                end else rx_count<=rx_count-1'b1;
                3: if (rx_count==0) begin
                    if (rx_sync) begin
                        rx_byte<=rx_shift;
                        rx_valid<=1;
                    end
                    rx_state<=0;
                end else rx_count<=rx_count-1'b1;
            endcase
            case (tx_state)
                0: if (tx_valid) begin
                    tx_shift<=tx_byte;
                    tx_bit<=0;
                    tx<=0;
                    tx_count<=CLKS_PER_BIT-1;
                    tx_state<=1;
                end
                1: if (tx_count==0) begin
                    tx<=tx_shift[tx_bit];
                    tx_count<=CLKS_PER_BIT-1;
                    if (tx_bit==7) tx_state<=2;
                    else tx_bit<=tx_bit+1'b1;
                end else tx_count<=tx_count-1'b1;
                2: if (tx_count==0) begin
                    tx<=1;
                    tx_count<=CLKS_PER_BIT-1;
                    tx_state<=3;
                end else tx_count<=tx_count-1'b1;
                3: if (tx_count==0) tx_state<=0;
                else tx_count<=tx_count-1'b1;
            endcase
        end
    end
endmodule
