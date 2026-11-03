`timescale 1ns/1ps
module tb_fsr_strike_detector;
    reg clk = 0;
    reg rst_n = 0;
    reg sample_valid = 0;
    reg [2:0] sample_channel = 0;
    reg [11:0] sample_value = 0;
    wire strike_valid;
    wire [2:0] strike_channel;
    wire [7:0] strike_velocity;
    wire [6:0] pressed;
    integer event_count = 0;
    reg [2:0] last_channel;
    reg [7:0] first_velocity, last_velocity;
    reg [7:0] slow_velocity;
    integer k;

    always #5 clk = ~clk;
    fsr_strike_detector #(
        .CAL_SAMPLES(2), .PEAK_SAMPLES(2), .REARM_SAMPLES(3),
        .ON_THRESHOLD(12'd200), .OFF_THRESHOLD(12'd50)
    ) dut (
        .clk(clk), .rst_n(rst_n), .sample_valid(sample_valid),
        .sample_channel(sample_channel), .sample_value(sample_value),
        .strike_valid(strike_valid), .strike_channel(strike_channel),
        .strike_velocity(strike_velocity), .pressed(pressed)
    );

    always @(negedge clk)
        if (strike_valid) begin
            event_count = event_count + 1;
            last_channel = strike_channel;
            last_velocity = strike_velocity;
        end

    task put;
        input [2:0] ch;
        input [11:0] val;
        begin
            @(negedge clk);
            sample_channel = ch;
            sample_value = val;
            sample_valid = 1;
            @(negedge clk);
            sample_valid = 0;
        end
    endtask

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        put(0, 12'd1000); put(0, 12'd1000);
        put(1, 12'd500); put(1, 12'd500);
        put(0, 12'd1080); put(0, 12'd1190);
        if (event_count != 0) $fatal(1, "idle noise triggered strike");

        put(0, 12'd1230); // cross threshold
        put(0, 12'd1500); // rise to peak
        put(0, 12'd1400); // capture peak
        if (event_count != 1 || last_channel != 0)
            $fatal(1, "first strike missing or wrong channel");
        if (pressed[0] !== 1'b1)
            $fatal(1, "pressed pad must remain active after strike");
        first_velocity = last_velocity;
        for (k = 0; k < 5; k = k + 1) put(0, 12'd1500);
        if (event_count != 1) $fatal(1, "held pad retriggered");

        put(1, 12'd900); put(1, 12'd1000); put(1, 12'd800);
        if (event_count != 2 || last_channel != 1)
            $fatal(1, "independent channel failed");

        for (k = 0; k < 4; k = k + 1) put(0, 12'd1000);
        if (pressed[0] !== 1'b0)
            $fatal(1, "released pad must lower its pressure gate");
        put(0, 12'd1300); put(0, 12'd2300); put(0, 12'd2100);
        if (event_count != 3 || last_channel != 0 ||
            last_velocity <= first_velocity)
            $fatal(1, "stronger tap must be louder: light=%0d heavy=%0d",
                   first_velocity, last_velocity);

        // Voltage-only trial: equal peak pressure gives equal velocity even
        // when one press rises faster than the other.
        for (k = 0; k < 5; k = k + 1) put(0, 12'd1000);
        put(0, 12'd1100);
        put(0, 12'd1210); // slow threshold crossing
        put(0, 12'd1300);
        put(0, 12'd1500); // peak excursion 500
        if (event_count != 4) $fatal(1, "slow strike missing");
        slow_velocity = last_velocity;
        for (k = 0; k < 5; k = k + 1) put(0, 12'd1000);
        put(0, 12'd1500); // same peak, faster rise
        put(0, 12'd1500);
        put(0, 12'd1500);
        if (event_count != 5 || last_velocity != slow_velocity)
            $fatal(1, "equal-peak taps must have equal velocity: slow=%0d fast=%0d",
                   slow_velocity, last_velocity);

        for (k = 0; k < 5; k = k + 1) put(0, 12'd1000);
        for (k = 1010; k <= 1320; k = k + 10) put(0, k[11:0]);
        repeat (4) put(0, 12'd1320);
        if (event_count != 6 || pressed[0] !== 1'b1)
            $fatal(1, "slow pressure ramp was swallowed by baseline tracking");
        $display("PASS: FSR voltage-only velocity, slow press, release and rearm");
        $finish;
    end
endmodule
