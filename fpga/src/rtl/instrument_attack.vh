// Shared by live polyphony and offline songs; no phase reset or accent peak.
// Reed: zero-slope rise to37.5% in2.667ms, then a21.333ms breath/body bloom.
// Bow retains its5.333ms curve. Onset latency is checked at actual I2S output.
function [15:0] instrument_attack_samples;
    input harmonica;
    begin instrument_attack_samples=harmonica ? 16'd1152 : 16'd256; end
endfunction

function [15:0] instrument_attack;
    input [15:0] age,from_level,target;
    input harmonica;
    reg [15:0] t,distance,curve,s_curve;
    reg [31:0] square;
    reg signed [16:0] delta;
    reg signed [33:0] blend;
    begin
        // Quadratic S: continuous value and zero slope at both endpoints.
        // Its midpoint is 50%; unlike an onset boost it cannot overshoot.
        t=harmonica ? (age<128 ? {age[6:0],9'd0} : ((age-16'd128)<<6)) : {age[7:0],8'd0};
        distance=t[15] ? ~t : t;
        square=distance*distance;
        s_curve=t[15] ? 16'd65535-square[30:15] : square[30:15];
        curve=harmonica ? (age<128 ? (s_curve>>2)+(s_curve>>3) :
            16'd24576+(s_curve>>1)+(s_curve>>3)) : s_curve;
        delta=$signed({1'b0,target})-$signed({1'b0,from_level});
        blend=delta*$signed({1'b0,curve});
        instrument_attack=age>=instrument_attack_samples(harmonica) ?
            target : from_level+(blend>>>16);
    end
endfunction
