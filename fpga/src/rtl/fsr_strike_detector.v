// Eight independent, scanned pressure channels -> one-cycle strike events.
// Samples must arrive with the same channel order each sweep. The selected
// resistor divider must make a stronger press produce a larger adjusted code;
// use INVERT=1 only when the physical circuit has the opposite polarity.
// Thresholds are ADC codes relative to a slowly tracked idle baseline.
module fsr_strike_detector #(
    parameter integer INVERT = 0,
    parameter integer CAL_SAMPLES = 16,
    parameter integer PEAK_SAMPLES = 4,
    parameter integer REARM_SAMPLES = 32,
    parameter integer EARLY_ENABLE = 0,
    parameter integer EARLY_MIN_FOLLOW = 2,
    parameter [11:0] EARLY_PEAK_MARGIN = 12'd64,
    parameter [11:0] ON_THRESHOLD = 12'd280,
    parameter [11:0] OFF_THRESHOLD = 12'd100
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        sample_valid,
    input  wire [2:0]  sample_channel,
    input  wire [11:0] sample_value,
    output reg         strike_valid,
    output reg  [2:0]  strike_channel,
    output reg  [7:0]  strike_velocity,
    output reg         level_valid,
    output reg  [2:0]  level_channel,
    output reg  [7:0]  level_velocity,
    output wire [6:0]  pressed,
    output reg         strike_early,
    output reg         pressure_valid,
    output reg [2:0]   pressure_channel,
    output reg [7:0]   pressure_value
);
    localparam integer CAL_BITS = (CAL_SAMPLES < 2) ? 1 : $clog2(CAL_SAMPLES + 1);
    localparam integer PEAK_BITS = (PEAK_SAMPLES < 2) ? 1 : $clog2(PEAK_SAMPLES + 1);
    localparam integer REARM_BITS = (REARM_SAMPLES < 2) ? 1 : $clog2(REARM_SAMPLES + 1);
    reg [11:0] baseline [0:7];
    reg [11:0] peak [0:7];
    reg [11:0] previous_excursion [0:7];
    reg [11:0] peak_rise [0:7];
    reg [CAL_BITS-1:0] cal_count [0:7];
    reg [PEAK_BITS-1:0] peak_left [0:7];
    reg [REARM_BITS-1:0] rearm_left [0:7];
    reg armed [0:7];
    reg early_fired [0:7];
    reg [1:0] settled [0:7];
    integer i;
    genvar g;
    generate for (g = 0; g < 7; g = g + 1) begin: press_outputs
        assign pressed[g] = (cal_count[g] == CAL_SAMPLES) && !armed[g];
    end endgenerate

    wire [11:0] adjusted = INVERT ? (12'hfff - sample_value) : sample_value;
    wire [11:0] current_baseline = baseline[sample_channel];
    wire [11:0] excursion = adjusted > current_baseline
        ? adjusted - current_baseline : 12'd0;
    wire [11:0] updated_peak = excursion > peak[sample_channel]
        ? excursion : peak[sample_channel];
    wire [11:0] rise = excursion > previous_excursion[sample_channel]
        ? excursion - previous_excursion[sample_channel] : 12'd0;
    wire [11:0] updated_rise = rise > peak_rise[sample_channel]
        ? rise : peak_rise[sample_channel];
    wire signed [13:0] idle_error = $signed({2'b00, adjusted}) -
                                    $signed({2'b00, current_baseline});
    // Divide toward zero so a small negative noise excursion does not
    // steadily drag the baseline down by one code at every sample.
    wire signed [13:0] idle_step = idle_error < 0
        ? -((-idle_error) >>> 5) : (idle_error >>> 5);
    wire signed [13:0] baseline_sum =
        $signed({2'b00, current_baseline}) + idle_step;
    wire [11:0] next_baseline = baseline_sum < 0 ? 12'd0 :
        baseline_sum > 14'sd4095 ? 12'd4095 : baseline_sum[11:0];

    // Accepted curve and channel gains are compiled into the configuration
    // image. They do not need to be learned again after each power cycle.
    // BEGIN GENERATED PRESSURE PROFILE
    localparam [31:0] PRESSURE_PROFILE_ID=32'h4af30002;
// Generated accepted fixed-point response; stored in FPGA configuration.
function [7:0] pressure_velocity;
    input [11:0] force_code;
    reg [11:0] delta;
    reg [7:0] base_level;
    reg [10:0] slope;
    reg [18:0] scaled;
    begin
        if (force_code < 12'd281) begin
            base_level=8'd16;
            delta=0;
            slope=11'd0;
        end
        else if (force_code < 12'd600) begin
            base_level=8'd16;
            delta=force_code-12'd280;
            slope=11'd45;
        end
        else if (force_code < 12'd819) begin
            base_level=8'd30;
            delta=force_code-12'd600;
            slope=11'd140;
        end
        else if (force_code < 12'd1024) begin
            base_level=8'd60;
            delta=force_code-12'd819;
            slope=11'd799;
        end
        else if (force_code < 12'd1050) begin
            base_level=8'd220;
            delta=force_code-12'd1024;
            slope=11'd1379;
        end
        else begin
            base_level=8'd255;
            delta=0;
            slope=11'd0;
        end
        scaled=delta*slope;
        pressure_velocity=base_level+scaled[17:10];
    end
endfunction
function [9:0] pressure_gain_q8;
    input [2:0] channel;
    begin
        case(channel)
            3'd0: pressure_gain_q8=10'd256;
            3'd1: pressure_gain_q8=10'd256;
            3'd2: pressure_gain_q8=10'd256;
            3'd3: pressure_gain_q8=10'd256;
            3'd4: pressure_gain_q8=10'd256;
            3'd5: pressure_gain_q8=10'd256;
            3'd6: pressure_gain_q8=10'd256;
            default: pressure_gain_q8=10'd256;
        endcase
    end
endfunction
function [7:0] pad_velocity;
    input [2:0] channel;
    input [11:0] force_code;
    reg [17:0] scaled_level;
    begin
        scaled_level=pressure_velocity(force_code)*pressure_gain_q8(channel);
        pad_velocity=scaled_level[17:8]>10'd255 ? 8'd255 : scaled_level[15:8];
    end
endfunction

    // END GENERATED PRESSURE PROFILE

    wire peak_settling = excursion >= ON_THRESHOLD &&
                         excursion <= previous_excursion[sample_channel];
    wire [1:0] next_settled = !peak_settling ? 2'd0 :
        settled[sample_channel] == 2'd3 ? 2'd3 : settled[sample_channel]+1'b1;
    wire [12:0] early_floor = {1'b0,ON_THRESHOLD}+{1'b0,EARLY_PEAK_MARGIN};
    // Conservative provisional-peak estimate: no derivative-dependent accent
    // or untrained positive extrapolation. Unsettled rises keep legacy timing.
    wire early_confident = EARLY_ENABLE != 0 && sample_channel < 3'd7 &&
        PEAK_SAMPLES > EARLY_MIN_FOLLOW && peak_left[sample_channel] > 1 &&
        !early_fired[sample_channel] && next_settled >= EARLY_MIN_FOLLOW &&
        {1'b0,updated_peak} >= early_floor;

    function [7:0] velocity_code;
        input [11:0] force_code;
        input [11:0] rise_code;
        begin
            // Preserve the captured peak-window timing; rise is deliberately
            // ignored so equal peak voltages have equal velocity codes.
            velocity_code = pressure_velocity(force_code);
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            strike_valid <= 1'b0;
            strike_channel <= 3'd0;
            strike_velocity <= 8'd0;
            strike_early <= 1'b0;
            pressure_valid<=0;pressure_channel<=0;pressure_value<=0;
            level_valid <= 1'b0;
            level_channel <= 3'd0;
            level_velocity <= 8'd0;
            for (i = 0; i < 8; i = i + 1) begin
                baseline[i] <= 12'd0;
                peak[i] <= 12'd0;
                previous_excursion[i] <= 12'd0;
                peak_rise[i] <= 12'd0;
                cal_count[i] <= {CAL_BITS{1'b0}};
                peak_left[i] <= {PEAK_BITS{1'b0}};
                rearm_left[i] <= {REARM_BITS{1'b0}};
                armed[i] <= 1'b0;
                early_fired[i] <= 1'b0;
                settled[i] <= 2'd0;
            end
        end else begin
            strike_valid <= 1'b0;
            strike_early <= 1'b0;
            pressure_valid<=0;
            level_valid <= 1'b0;
            if (sample_valid) begin
                // Current pressure is separate from peak-window corrections.
                // It includes falling values and cannot create another strike.
                if(sample_channel<7 && cal_count[sample_channel]==CAL_SAMPLES)begin
                    pressure_valid<=1;pressure_channel<=sample_channel;
                    pressure_value<=excursion<=OFF_THRESHOLD ? 0 : pad_velocity(sample_channel,excursion);
                end
                if (sample_channel < 3'd7 &&
                    cal_count[sample_channel] == CAL_SAMPLES &&
                    !armed[sample_channel] && excursion >= ON_THRESHOLD) begin
                    level_valid <= 1'b1;
                    level_channel <= sample_channel;
                    level_velocity <= pad_velocity(sample_channel,excursion);
                end
                previous_excursion[sample_channel] <= excursion;
                if (cal_count[sample_channel] < CAL_SAMPLES) begin
                    // Startup acquisition suppresses a spurious first tap.
                    baseline[sample_channel] <= adjusted;
                    previous_excursion[sample_channel] <= 12'd0;
                    cal_count[sample_channel] <= cal_count[sample_channel] + 1'b1;
                    armed[sample_channel] <= 1'b1;
                end else if (peak_left[sample_channel] != 0) begin
                    peak[sample_channel] <= updated_peak;
                    peak_rise[sample_channel] <= updated_rise;
                    settled[sample_channel] <= next_settled;
                    if (peak_left[sample_channel] == 1) begin
                        peak_left[sample_channel] <= {PEAK_BITS{1'b0}};
                        rearm_left[sample_channel] <= REARM_SAMPLES;
                        if(!early_fired[sample_channel])begin
                            strike_valid <= 1'b1;
                            strike_channel <= sample_channel;
                            strike_velocity <= pad_velocity(sample_channel,updated_peak);
                        end else begin
                            // Correct the existing voice, never emit a second
                            // NOTE_ON. The allocator only accepts upward level
                            // corrections; its existing sample-rate slew stays.
                            level_valid <= 1'b1;
                            level_channel <= sample_channel;
                            level_velocity <= pad_velocity(sample_channel,updated_peak);
                        end
                    end else begin
                        peak_left[sample_channel] <= peak_left[sample_channel] - 1'b1;
                        if(early_confident)begin
                            strike_valid<=1'b1;strike_early<=1'b1;
                            strike_channel<=sample_channel;
                            strike_velocity<=pad_velocity(sample_channel,updated_peak);
                            early_fired[sample_channel]<=1'b1;
                        end
                    end
                end else begin
                    if (rearm_left[sample_channel] != 0)
                        rearm_left[sample_channel] <= rearm_left[sample_channel] - 1'b1;

                    if (armed[sample_channel] && excursion >= ON_THRESHOLD) begin
                        armed[sample_channel] <= 1'b0;
                        peak[sample_channel] <= excursion;
                        peak_rise[sample_channel] <= rise;
                        early_fired[sample_channel] <= 1'b0;
                        settled[sample_channel] <= 2'd0;
                        peak_left[sample_channel] <= PEAK_SAMPLES;
                    end else if (!armed[sample_channel] &&
                                 rearm_left[sample_channel] == 0 &&
                                 excursion <= OFF_THRESHOLD) begin
                        armed[sample_channel] <= 1'b1;
                        // A rising FSR value may be a very slow intentional
                        // press. Do not chase it as an idle baseline drift.
                        if (adjusted < current_baseline)
                            baseline[sample_channel] <= next_baseline;
                    end else if (armed[sample_channel] &&
                                 excursion <= OFF_THRESHOLD)
                        if (adjusted < current_baseline)
                            baseline[sample_channel] <= next_baseline;
                end
            end
        end
    end
endmodule
