`timescale 1ns/1ps
module tb_headphone_check;
    reg clk=0,rst_n=0,key0=1,key1=1;
    wire bclk,ws,sd,pa;
    integer frames=0,heard0=0,heard1=0;
    always #5 clk=~clk;
    headphone_check_core #(.DEBOUNCE_CYCLES(3),.WARMUP_FRAMES(3)) dut(
        .clk_audio(clk),.rst_n(rst_n),.key0_n(key0),.key1_n(key1),
        .HP_BCK(bclk),.HP_WS(ws),.HP_DIN(sd),.PA_EN(pa));
    always @(negedge clk)if(rst_n && dut.sample_tick)begin
        frames=frames+1;
        if(dut.monitor_sample>16383 || dut.monitor_sample< -16384)$fatal(1,"monitor gain overflow");
        if(!key0 && dut.harmonica!=0)heard0=heard0+1;
        if(!key1 && dut.erhu!=0)heard1=heard1+1;
    end
    initial begin
        repeat(3)@(negedge clk);
        if(pa!==1)$fatal(1,"amplifier must be off in reset");
        rst_n=1;wait(frames==2);@(negedge clk);
        if(pa!==1)$fatal(1,"headphone warmup was bypassed");
        wait(frames==20);@(negedge clk);
        if(pa!==0 || dut.monitor_sample!==0)$fatal(1,"idle must be silent after warmup");
        key0=0;wait(frames==600);@(negedge clk);
        if(heard0<100 || heard1!=0)$fatal(1,"KEY0 did not produce independent harmonica");
        key1=0;wait(frames==1200);@(negedge clk);
        if(heard1<100)$fatal(1,"KEY1 did not produce erhu");
        key0=1;key1=1;wait(frames==12000);@(negedge clk);
        if(dut.monitor_sample!==0)$fatal(1,"released check notes did not return to silence");
        rst_n=0;#1;if(pa!==1)$fatal(1,"reset did not disable amplifier");
        $display("PASS: standalone headphone warmup, silent idle, two local keys, bounded gain and release");$finish;
    end
    initial begin #40000000;$fatal(1,"headphone check timeout");end
endmodule
