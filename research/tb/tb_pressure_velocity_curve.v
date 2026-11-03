`timescale 1ns/1ps
module tb_pressure_velocity_curve;
    reg clk = 0, rst_n = 0, sample_valid = 0;
    reg [2:0] sample_channel = 0;
    reg [11:0] sample_value = 0;
    wire strike_valid, level_valid;
    wire [2:0] strike_channel, level_channel;
    wire [7:0] strike_velocity, level_velocity;
    wire [6:0] pressed;
    integer code, last_value, value;

    fsr_strike_detector #(.ON_THRESHOLD(12'd280)) dut (
        .clk(clk), .rst_n(rst_n), .sample_valid(sample_valid),
        .sample_channel(sample_channel), .sample_value(sample_value),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .level_valid(level_valid),
        .level_channel(level_channel), .level_velocity(level_velocity),
        .pressed(pressed)
    );
    fsr_strike_detector #(.ON_THRESHOLD(12'd200)) dut_low_threshold (
        .clk(clk), .rst_n(rst_n), .sample_valid(sample_valid),
        .sample_channel(sample_channel), .sample_value(sample_value),
        .strike_valid(), .strike_channel(), .strike_velocity(),
        .level_valid(), .level_channel(), .level_velocity(), .pressed()
    );

    task check;
        input [11:0] adc_code;
        input integer target;
        begin
            value = dut.pressure_velocity(adc_code);
            if (value < target - 2 || value > target + 2)
                $fatal(1, "curve code=%0d expected~%0d got=%0d",
                       adc_code, target, value);
        end
    endtask

    initial begin
        check(12'd280, 16);
        check(12'd600, 30);
        check(12'd819, 50);   // observed 1.5 V terminal bin starts here
        check(12'd1023, 84);
        check(12'd1024, 85);  // no loudness step at the bin boundary
        check(12'd1125, 254);
        check(12'd1126, 255); // measured hard press straddles this code
        check(12'd1229, 255);
        check(12'd4095, 255);
        if (dut.pressure_velocity(12'd819) != 8'd50 ||
            dut.pressure_velocity(12'd1024) != 8'd85 ||
            dut.pressure_velocity(12'd1126) != 8'd255)
            $fatal(1, "measured-bin anchor codes are not exact");
        if (dut.pressure_velocity(12'd1126) <
            3 * dut.pressure_velocity(12'd1023))
            $fatal(1, "hard/normal digital amplitude ratio is too small");
        if (dut_low_threshold.pressure_velocity(12'd818) >
            dut_low_threshold.pressure_velocity(12'd819))
            $fatal(1, "custom trigger threshold makes curve non-monotonic");
        last_value = 0;
        for (code = 280; code <= 4095; code = code + 1) begin
            value = dut.pressure_velocity(code[11:0]);
            if (value < last_value)
                $fatal(1, "curve is not monotonic at code=%0d", code);
            last_value = value;
        end
        if (dut.velocity_code(12'd2948, 12'd0) == 0)
            $fatal(1, "slow pressure must remain audible");
        if (dut.velocity_code(12'd2948, 12'd512) !=
            dut.velocity_code(12'd2948, 12'd0))
            $fatal(1, "voltage-only trial must not add a rise accent");
        if (dut.pressure_velocity(12'd1024) -
            dut.pressure_velocity(12'd1023) != 8'd1 ||
            dut.pressure_velocity(12'd1126) -
            dut.pressure_velocity(12'd1125) != 8'd1 ||
            dut.pressure_velocity(12'd1229) !=
            dut.pressure_velocity(12'd1228))
            $fatal(1, "velocity curve has a step at a bin boundary");
        if (dut.velocity_code(12'd4095, 12'd4095) != 8'd255)
            $fatal(1, "maximum strike velocity must saturate at 255");
        $display("PASS: measured ADC bins map to separated velocities");
        $finish;
    end
endmodule
