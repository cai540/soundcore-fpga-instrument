`timescale 1ns/1ps
module tb_pressure_expression32;
    reg clk=0,rst_n=0,tick=0,pv=0;
    always #5 clk=~clk;
    reg [31:0] gate=0,remote=0;
    reg [95:0] zones=0;
    reg [255:0] attack=0;
    reg [2:0] channel=0;reg [7:0] value=0;
    wire [255:0] amplitude,expression;
    integer i,k,before_level,held;
    pressure_expression32 #(.ATTACK_HOLD_FRAMES(8),.CONTROL_INTERVAL(2)) dut(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.remote_owner(remote),
        .voice_zone(zones),.attack_velocity(attack),.pressure_valid(pv),.pressure_channel(channel),
        .pressure_velocity(value),.performance_velocity(amplitude),.expression(expression));
    task frames;input integer n;
        begin for(k=0;k<n;k=k+1)begin @(negedge clk);tick=1;@(negedge clk);tick=0;repeat(254)@(negedge clk);end end
    endtask
    task pressure;input integer ch;input integer level;
        begin @(negedge clk);channel=ch;value=level;pv=1;@(negedge clk);pv=0;end
    endtask
    initial begin
        for(i=0;i<32;i=i+1)begin zones[i*3 +: 3]=i%7;attack[i*8 +: 8]=200;end
        repeat(3)@(negedge clk);rst_n=1;
        for(i=0;i<7;i=i+1)pressure(i,200);
        frames(110);gate=32'hffffffff;remote=32'h80000000;
        frames(1);if(amplitude!==attack || expression!==attack)$fatal(1,"32 attack contexts not initialized");
        pressure(0,40);frames(6);
        if(amplitude[7:0]!=200)$fatal(1,"short-tap attack strength was changed");
        // All pad0 owners move together; phone owner remains independent.
        frames(220);
        if(amplitude[7:0]<37 || amplitude[7:0]>46)$fatal(1,"decreasing pressure not followed");
        for(i=0;i<32;i=i+1)begin
            if(i%7==0 && amplitude[i*8 +: 8]>46)$fatal(1,"pad owner missed falling expression");
            if(i%7!=0 && amplitude[i*8 +: 8]<195)$fatal(1,"another pad was changed");
        end
        if(amplitude[255:248]!=200)$fatal(1,"physical pressure changed remote owner");
        before_level=amplitude[7:0];pressure(0,before_level+1);frames(20);
        if(amplitude[7:0]!=before_level)$fatal(1,"deadband did not reject jitter");
        pressure(0,240);frames(220);
        if(amplitude[7:0]<234 || amplitude[7:0]>243)$fatal(1,"rising expression not followed");
        pressure(0,255);frames(100);
        for(i=0;i<31;i=i+1)if(i%7==0 && amplitude[i*8+:8]!==8'd255)
            $fatal(1,"full pressure stalled below 255 on voice %0d",i);
        if(amplitude[255:248]!==8'd200)$fatal(1,"full pad pressure changed remote voice");
        held=amplitude[7:0];gate[0]=0;pressure(0,0);frames(280);
        if(amplitude[7:0]!=held)$fatal(1,"release tail amplitude was not frozen");
        if(dut.pad_smooth[0]!==8'd0)$fatal(1,"zero pressure stalled above zero");
        gate[0]=1;attack[7:0]=90;frames(1);
        if(amplitude[7:0]!=90)$fatal(1,"reused voice retained stale attack");
        rst_n=0;#1;if(amplitude!==0 || expression!==0)$fatal(1,"reset leaked old state");
        $display("PASS:32 independent contexts, attack hold, rising/falling pressure, exact 0/255 endpoints, deadband, remote isolation, frozen release, reuse/reset");$finish;
    end
endmodule
