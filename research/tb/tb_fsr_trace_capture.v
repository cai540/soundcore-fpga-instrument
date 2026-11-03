`timescale 1ns/1ps
module tb_fsr_trace_capture;
    reg clk=0,rst_n=0,arm=0,trigger=0,valid=0,read_en=0;
    reg [2:0] ch=0;
    reg [11:0] value=0;
    reg [3:0] index=0;
    wire rv,active,done;
    wire [47:0] data;
    wire [4:0] count;
    wire [31:0] trigger_clock;
    integer i,k,mode,reads=0,markers,last_time;
    reg [47:0] first_word;
    always #5 clk=~clk;
    fsr_trace_capture #(.ADDR_BITS(4),.POST_SAMPLES(4)) dut(
        .clk(clk),.rst_n(rst_n),.arm(arm),.trigger(trigger),.sample_valid(valid),
        .sample_channel(ch),.sample_value(value),.read_en(read_en),.read_index(index),
        .read_valid(rv),.read_data(data),.active(active),.done(done),.record_count(count),.trigger_clock(trigger_clock));
    task put;
        input integer n;
        input integer trig;
        begin @(negedge clk);value=n;ch=n%7;valid=1;trigger=trig;@(negedge clk);valid=0;trigger=0;end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(mode=0;mode<3;mode=mode+1)begin
            @(negedge clk);arm=1;@(negedge clk);arm=0;
            // 24 pre-samples wrap a16-entry ring. The third run is unwrapped.
            for(i=0;i<(mode==2 ? 2 :24);i=i+1)put(i,0);
            if(mode==1)begin @(negedge clk);trigger=1;@(negedge clk);trigger=0;end
            for(k=0;k<4;k=k+1)put(i+k,mode!=1 && k==0);
            if(!done || active || count!=(mode==2?6:16))$fatal(1,"capture did not freeze correctly");
            markers=0;last_time=-1;
            for(k=0;k<count;k=k+1)begin
                @(negedge clk);index=k;read_en=1;@(posedge clk);#1;
                if(!rv || data[11:0]!=(mode==2?k:12+k))$fatal(1,"chronological read mismatch mode=%0d index=%0d got=%0d",mode,k,data[11:0]);
                if(data[14:12]!=(data[11:0]%7) || (k!=0 && data[47:16]<=last_time))$fatal(1,"bad channel/timestamp");
                last_time=data[47:16];if(data[15])markers=markers+1;
                if(k==0)first_word=data;reads=reads+1;
            end
            @(negedge clk);read_en=0;
            if(markers!=1 || trigger_clock==0)$fatal(1,"trigger marker missing or duplicated");
            put(999,1); // A frozen capture must not be overwritten.
            @(negedge clk);read_en=1;index=0;@(posedge clk);#1;
            if(!rv || data!==first_word)$fatal(1,"frozen capture overwritten");
            @(negedge clk);arm=1;@(posedge clk);#1;
            if(rv || done || count!=0)$fatal(1,"rearm retained old read/status");
            @(negedge clk);arm=0;read_en=0;
        end
        $display("PASS: %0d chronological records; wrap, early trigger, aligned/unaligned event, synchronous read, freeze and rearm",reads);
        $finish;
    end
endmodule
