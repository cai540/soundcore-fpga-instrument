`timescale 1ns/1ps
module tb_pressure_saved_profile;
    reg clk=0,rst_n=0,valid=0;
    reg [2:0] ch=0;
    reg [11:0] value=1000;
    always #5 clk=~clk;
    wire fire,ref_fire,level,ref_level,early;
    wire [2:0] pad,ref_pad,level_pad,ref_level_pad;
    wire [7:0] vel,ref_vel,level_vel,ref_level_vel;
    wire [6:0] pressed,ref_pressed;
    reg [7:0] saved[0:4095];
    integer code,pad_i,n,checks=0;
    fsr_strike_detector #(.CAL_SAMPLES(2),.PEAK_SAMPLES(4),.REARM_SAMPLES(3)) dut(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(value),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(vel),.level_valid(level),
        .level_channel(level_pad),.level_velocity(level_vel),.pressed(pressed),.strike_early(early));
    fsr_strike_detector_legacy #(.CAL_SAMPLES(2),.PEAK_SAMPLES(4),.REARM_SAMPLES(3)) reference(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(value),
        .strike_valid(ref_fire),.strike_channel(ref_pad),.strike_velocity(ref_vel),.level_valid(ref_level),
        .level_channel(ref_level_pad),.level_velocity(ref_level_vel),.pressed(ref_pressed));
    always @(posedge clk)begin
        #1;
        if(rst_n)begin
            if({fire,pad,vel,level,level_pad,level_vel,pressed}!==
               {ref_fire,ref_pad,ref_vel,ref_level,ref_level_pad,ref_level_vel,ref_pressed})
                $fatal(1,"disabled detector changed legacy stream n=%0d",n);
            if(early)$fatal(1,"early default must be disabled");
        end
    end
    task put;
        input [2:0] channel;
        input [11:0] adc;
        begin @(negedge clk);ch=channel;value=adc;valid=1;@(negedge clk);valid=0;end
    endtask
    initial begin
        $readmemh("build/early_pressure_20261028/saved_curve.mem",saved);
        for(code=0;code<4096;code=code+1)begin
            if(dut.pressure_velocity(code)!==reference.pressure_velocity(code) ||
               dut.pressure_velocity(code)!==saved[code])$fatal(1,"saved curve changed code %0d",code);
            for(pad_i=0;pad_i<7;pad_i=pad_i+1)begin
                if(dut.pad_velocity(pad_i,code)!==saved[code])$fatal(1,"unexpected channel gain");
                checks=checks+1;
            end
        end
        repeat(3)@(negedge clk);rst_n=1;
        for(pad_i=0;pad_i<7;pad_i=pad_i+1)begin put(pad_i,1000);put(pad_i,1000);end
        for(n=0;n<3500;n=n+1)begin
            if(n==1700)begin rst_n=0;repeat(3)@(negedge clk);rst_n=1;end
            // Repeated quiet, ramps, plateaus, releases and all channels.
            put(n%7, (n%91)<21 ? 1000 : (n%91)<56 ? 1000+(n%35)*30 : 1600);
        end
        $display("PASS: saved profile matches all4096 legacy curve values, %0d pad mappings, disabled stream/reset bit-exact; no manual calibration input",checks);
        $finish;
    end
endmodule
