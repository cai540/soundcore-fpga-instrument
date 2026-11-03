`timescale 1ns/1ps
module tb_oled_i2c_write2;
    reg clk=0, rst_n=0, start=0, slave_ack=1;
    reg [7:0] control_byte=8'h00, payload_byte=8'hAE;
    tri1 scl, sda;
    wire busy, done, ack_ok;
    integer done_count=0;
    always #5 clk=~clk;
    oled_i2c_write2 #(.CLK_DIV(2)) dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .address_write(8'h78),
        .control_byte(control_byte), .payload_byte(payload_byte),
        .scl(scl), .sda(sda), .busy(busy), .done(done), .ack_ok(ack_ok)
    );
    assign sda = slave_ack && (dut.state == 4 || dut.state == 5 || dut.state == 9) ? 1'b0 : 1'bz;
    always @(posedge clk) if (done) done_count=done_count+1;
    task transaction;
        input [7:0] ctl, data;
        begin
            wait(!busy);
            @(negedge clk); control_byte=ctl; payload_byte=data; start=1;
            @(negedge clk); start=0;
            wait(done);
            wait(!busy);
            @(posedge clk);
            @(negedge clk);
        end
    endtask
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        transaction(8'h00,8'hAE);
        if (done_count != 1 || !ack_ok || busy)
            $fatal(1,"command transaction ACK failed count=%0d ack=%b busy=%b",done_count,ack_ok,busy);
        slave_ack=0;
        transaction(8'h40,8'h7E);
        if (done_count != 2 || ack_ok || busy)
            $fatal(1,"NACK reporting failed");
        $display("PASS: OLED I2C two-byte write, ACK and NACK");
        $finish;
    end
endmodule
