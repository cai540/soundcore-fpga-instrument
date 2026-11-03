`timescale 1ns/1ps
module tb_pressure_calibrated_profile;
    reg clk=0,rst_n=0,valid=0;
    always #5 clk=~clk;
    reg [2:0] channel=6;
    reg [11:0] value=1000;
    wire fire,level,pressure_valid;
    wire [2:0] pad,level_pad,pressure_pad;
    wire [7:0] velocity,level_velocity,pressure_value;
    wire [6:0] pressed;
    reg [7:0] legacy[0:4095];
    reg [7:0] expected[0:28671];
    integer code,ch,previous,actual,reference,normalized,checks=0,events=0;
    fsr_strike_detector #(.CAL_SAMPLES(2),.PEAK_SAMPLES(4),
        .REARM_SAMPLES(2),.EARLY_ENABLE(1)) dut(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),
        .sample_channel(channel),.sample_value(value),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(velocity),
        .level_valid(level),.level_channel(level_pad),.level_velocity(level_velocity),
        .pressed(pressed),.pressure_valid(pressure_valid),
        .pressure_channel(pressure_pad),.pressure_value(pressure_value));
    always @(posedge clk)begin
        #1;
        if(rst_n && fire)begin
            events=events+1;
            if(pad!==6 || velocity!==255)$fatal(1,"AI6 attack did not use calibrated span");
        end
        if(rst_n && level && level_pad==6 && value==2071 && level_velocity!==255)
            $fatal(1,"peak correction uses different calibration");
        if(rst_n && pressure_valid && pressure_pad==6 && value==2071 && pressure_value!==255)
            $fatal(1,"continuous pressure uses different calibration");
    end
    task put;
        input [11:0] sample;
        begin @(negedge clk);value=sample;valid=1;@(negedge clk);valid=0;end
    endtask
    initial begin
        $readmemh("build/early_pressure_20261028/saved_curve.mem",legacy);
        $readmemh("build/pressure_ai6_20261031/expected_pad_velocity.mem",expected);
        for(code=0;code<4096;code=code+1)
            if(dut.pressure_velocity(code)!==legacy[code])$fatal(1,"base curve changed code %0d",code);
        for(ch=0;ch<7;ch=ch+1)begin
            previous=0;
            for(code=0;code<4096;code=code+1)begin
                actual=dut.pad_velocity(ch,code);
                if(actual!==expected[ch*4096+code])$fatal(1,"fixed-point mismatch ch%0d code%0d",ch,code);
                if(actual<previous)$fatal(1,"nonmonotone calibrated pressure");
                if(ch<6 && actual!==legacy[code])$fatal(1,"another pad changed");
                normalized=dut.normalized_pressure(ch,code);
                // Independent exact measured ratio 41/39, with <=1 ADC-code
                // error allowed for the documented Q12 quantization.
                reference=ch==6 ? (code*41+19)/39 : code;
                if(reference>4095)reference=4095;
                if(normalized>reference+1 || normalized+1<reference)
                    $fatal(1,"span ratio mismatch ch%0d code%0d",ch,code);
                previous=actual;checks=checks+1;
            end
        end
        if(dut.pad_velocity(6,1071)!==255 || dut.pressure_velocity(1071)>=255)
            $fatal(1,"AI6 full-scale boundary did not improve");
        if(dut.normalized_pressure(6,4095)!==4095)$fatal(1,"high input wrapped instead of saturating");
        repeat(3)@(negedge clk);rst_n=1;
        put(1000);put(1000);
        repeat(8)put(2071);
        if(events!=1 || !pressed[6])$fatal(1,"AI6 onset/retrigger failure");
        repeat(8)put(1000);
        if(pressed[6] || events!=1 || pressure_value!==0)$fatal(1,"AI6 release failure");
        $display("PASS: 4096 base curve entries unchanged; %0d calibrated mappings; six identity pads; Q12 vs exact 41/39 ratio; AI6 attack/correction/hold full255 and release",checks);
        $finish;
    end
endmodule
