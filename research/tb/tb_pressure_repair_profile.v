`timescale 1ns/1ps
module tb_pressure_repair_profile;
    reg clk=0,rst_n=0,valid=0;always #5 clk=~clk;
    reg [2:0] channel=6;reg [11:0] value=1000;
    wire fire,level,pressure_valid;wire [2:0] pad,level_pad,pressure_pad;
    wire [7:0] velocity,level_velocity,pressure_value;wire [6:0] pressed;
    reg [7:0] legacy[0:4095];reg [7:0] expected[0:28671];
    integer code,ch,previous,actual,reference,normalized,checks=0,events=0;
    fsr_strike_detector #(.CAL_SAMPLES(2),.PEAK_SAMPLES(4),.REARM_SAMPLES(2),.EARLY_ENABLE(1)) dut(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(channel),.sample_value(value),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(velocity),.level_valid(level),
        .level_channel(level_pad),.level_velocity(level_velocity),.pressed(pressed),
        .pressure_valid(pressure_valid),.pressure_channel(pressure_pad),.pressure_value(pressure_value));
    always @(posedge clk)begin #1;if(rst_n && fire)begin events=events+1;
        if(pad!==6 || velocity!==255)$fatal(1,"AI6 attack differs from calibrated pressure");end end
    task put;input [11:0] sample;
        begin @(negedge clk);value=sample;valid=1;@(negedge clk);valid=0;end
    endtask
    initial begin
        $readmemh("build/early_pressure_20261028/saved_curve.mem",legacy);
        $readmemh("build/timbre_pressure_repair_20261101/pressure/expected_pad_velocity.mem",expected);
        for(code=0;code<4096;code=code+1)if(dut.pressure_velocity(code)!==legacy[code])$fatal(1,"base curve changed");
        for(ch=0;ch<7;ch=ch+1)begin previous=0;
            for(code=0;code<4096;code=code+1)begin
                actual=dut.pad_velocity(ch,code);normalized=dut.normalized_pressure(ch,code);
                reference=ch==6 ? (code*71+32)/64 : code;if(reference>4095)reference=4095;
                if(normalized!==reference || actual!==expected[ch*4096+code])$fatal(1,"mapping mismatch");
                if(actual<previous || (ch<6 && actual!==legacy[code]))$fatal(1,"other channel changed or mapping nonmonotone");
                previous=actual;checks=checks+1;
            end
        end
        if(dut.pad_velocity(6,1015)!==255 || dut.pad_velocity(6,1014)>=255)$fatal(1,"AI6 candidate endpoint wrong");
        repeat(3)@(negedge clk);rst_n=1;put(1000);put(1000);
        repeat(8)put(2015);
        if(events!=1 || !pressed[6] || level_velocity!==255 || pressure_value!==255)$fatal(1,"attack/visual/continuous mismatch");
        repeat(8)put(1600);
        if(pressure_value>=255 || events!=1)$fatal(1,"reduced force did not decrease or retriggered");
        repeat(8)put(1000);
        if(pressed[6] || pressure_value!==0 || events!=1)$fatal(1,"release failed");
        $display("PASS:%0d mappings; original curve/six channels unchanged; AI6 attack,visual and continuous pressure reach255 together; release/decline preserved",checks);$finish;
    end
endmodule
