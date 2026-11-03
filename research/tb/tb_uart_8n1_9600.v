`timescale 1ns/1ps
module tb_uart_8n1_9600;
    reg clk=0,rst_n=0,tx_valid=0;
    reg [7:0] tx_byte=0;
    wire line,rx_valid,tx_ready;
    wire [7:0] rx_byte;
    integer count=0;
    always #5 clk=~clk;
    uart_8n1_9600 #(.CLKS_PER_BIT(8)) dut (
        .clk(clk),.rst_n(rst_n),.rx(line),.rx_valid(rx_valid),
        .rx_byte(rx_byte),.tx(line),.tx_valid(tx_valid),
        .tx_byte(tx_byte),.tx_ready(tx_ready)
    );
    always @(posedge clk) if (rx_valid) begin
        if (count==0 && rx_byte!==8'hA5) $fatal(1,"first byte %h",rx_byte);
        if (count==1 && rx_byte!==8'h00) $fatal(1,"second byte %h",rx_byte);
        count=count+1;
    end
    task send;
        input [7:0] b;
        begin
            wait(tx_ready);
            @(negedge clk); tx_byte=b;tx_valid=1;
            @(negedge clk); tx_valid=0;
            wait(!tx_ready);
            wait(tx_ready);
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        send(8'hA5);send(8'h00);
        repeat(10) @(negedge clk);
        if(count!=2)$fatal(1,"UART received %0d bytes",count);
        $display("PASS: UART 9600 design, byte order and back-to-back loopback");
        $finish;
    end
endmodule
