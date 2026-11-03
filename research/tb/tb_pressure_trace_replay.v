`timescale 1ns/1ps
module tb_pressure_trace_replay;
    reg clk=0,rst_n=0,valid=0;
    always #5 clk=~clk;
    reg [15:0] rows[0:2927];
    reg [18:0] expected[0:2927];
    reg [2:0] ch=0;
    reg [11:0] adc=0;
    wire fire,early,lv;
    wire [2:0] pad,lp;
    wire [7:0] velocity,level;
    integer i,notes=0,earlies=0;
    fsr_strike_detector #(.EARLY_ENABLE(1)) dut(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(adc),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(velocity),
        .strike_early(early),.level_valid(lv),.level_channel(lp),.level_velocity(level));
    initial begin
        $readmemh("build/early_pressure_20261028/replay/input.mem",rows);
        $readmemh("build/early_pressure_20261028/replay/expected.mem",expected);
        repeat(3)@(negedge clk);rst_n=1;
        for(i=0;i<2928;i=i+1)begin
            @(negedge clk);ch=rows[i][14:12];adc=rows[i][11:0];valid=(ch!=7);
            @(posedge clk);#1;
            if(fire!==expected[i][18] || early!==expected[i][9] || lv!==expected[i][8])
                $fatal(1,"replay event differs at row%0d",i);
            if(fire)begin
                if(pad!==ch || velocity!==expected[i][17:10])$fatal(1,"replay strike differs at row%0d",i);
                notes=notes+1;if(early)earlies=earlies+1;
            end
            if(lv && (lp!==ch || level!==expected[i][7:0]))$fatal(1,"replay level differs at row%0d",i);
            @(negedge clk);valid=0;repeat(398)@(negedge clk);
        end
        if(notes!=42 || earlies!=21)$fatal(1,"saved trace event counts differ");
        $display("PASS: 2928 saved synthetic samples match offline replay, default16-sample automatic zero, 42 notes/21 early events");
        $finish;
    end
endmodule
