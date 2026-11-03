`timescale 1ns/1ps
module tb_realtime_notes;
    reg clk=0,rst_n=0,valid=0,ready=0;
    always #5 clk=~clk;
    reg [7:0] mask=0,attacks=0;
    wire [6:0] held;
    wire fire;
    wire [2:0] pad;
    wire [7:0] velocity;
    integer count=0,i;
    reg [6:0] fired=0;
    remote_note_bridge #(.REALTIME_ENABLED(1),.LEASE_CYCLES(1000),.PENDING_LIMIT_CYCLES(20)) dut(
        .clk(clk),.rst_n(rst_n),.write_allowed(1'b1),.command_valid(valid),.command_type(8'h24),
        .command_value(mask),.command_value2(attacks),.command_payload({32'd0,8'd190,attacks,mask}),
        .physical_strike(1'b0),.voice_ready(ready),.remote_pressed(held),
        .remote_strike_valid(fire),.remote_strike_channel(pad),.remote_strike_velocity(velocity));
    always @(posedge clk)if(rst_n && fire)begin
        if(velocity!=190)$fatal(1,"current strike velocity lost");
        count=count+1;fired[pad]=1;
    end
    task packet;
        input [6:0] m,a;
        begin @(negedge clk);mask=m;attacks=a;valid=1;@(negedge clk);valid=0;end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        // Congested voice bank: seven old taps are released before service.
        packet(7'h7f,7'h7f);packet(0,0);ready=1;repeat(10)@(negedge clk);
        if(count!=0 || held!=0)$fatal(1,"released backlog replayed");
        packet(7'b1010101,7'b1010101);repeat(8)@(negedge clk);
        if(count!=4 || fired!=7'b1010101)$fatal(1,"current chord missing count=%0d mask=%b",count,fired);
        packet(7'b1010101,0);repeat(6)@(negedge clk);
        if(count!=4)$fatal(1,"lease snapshot retriggered a note");
        ready=0;packet(2,2);repeat(25)@(negedge clk);ready=1;repeat(5)@(negedge clk);
        if(count!=4)$fatal(1,"expired voice request sounded late");
        ready=0;packet(0,0);packet(2,2);
        repeat(16)packet(2,0);
        ready=1;repeat(5)@(negedge clk);
        if(count!=4)$fatal(1,"held-state refresh kept expired request alive");
        packet(0,0);if(held!=0)$fatal(1,"release snapshot not authoritative");
        $display("PASS: current chord, authoritative release, no backlog, no lease retrigger, bounded voice wait");$finish;
    end
endmodule
