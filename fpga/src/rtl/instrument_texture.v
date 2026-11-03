// Algorithmic reed/bowed-string colour, not recorded PCM. The 32-voice
// engine services one context per voice slot; the offline voice uses one.
module instrument_texture #(
    parameter integer VOICES=1
) (
    input wire clk,rst_n,step_en,active,
    input wire [4:0] slot,
    input wire [31:0] phase,
    input wire [15:0] note_age,
    input wire [7:0] velocity,
    input wire timbre, // 1=reed with air, 0=bowed with friction
    output wire signed [15:0] wave_out,
    output wire signed [7:0] pitch_drift
);
    localparam integer INDEX_BITS=VOICES>1 ? $clog2(VOICES) : 1;
    wire [INDEX_BITS-1:0] index=slot[INDEX_BITS-1:0];
    reg [31:0] random_state[0:VOICES-1];
    reg signed [17:0] air_fast[0:VOICES-1],air_slow[0:VOICES-1];
    reg signed [25:0] wander[0:VOICES-1];
    reg signed [18:0] body_fast[0:VOICES-1],body_slow[0:VOICES-1];
    integer i;

    // A parabolic sine approximation. Every harmonic starts at a zero
    // crossing, with much less sharp-corner energy than a triangle/saw mix.
    function signed [15:0] sine;
        input [31:0] p;
        reg [31:0] q;
        reg [15:0] t;
        reg signed [16:0] x;
        reg [16:0] magnitude;
        reg signed [17:0] curvature;
        reg signed [34:0] product;
        begin
            q=p+32'h40000000;
            t=q[31] ? {~q[30:16],1'b0} : {q[30:16],1'b0};
            x=$signed({t[15]^1'b1,t^16'h8000});
            magnitude=x<0 ? -x : x;
            curvature=18'sd65536-$signed({1'b0,magnitude});
            product=x*curvature;
            sine=product>>>15;
        end
    endfunction
    wire signed [15:0] h1=sine(phase),h2=sine(phase<<1);
    wire signed [15:0] h3=sine((phase<<1)+phase),h4=sine(phase<<2);
    wire signed [15:0] h5=sine((phase<<2)+phase),h6=sine((phase<<2)+(phase<<1));
    wire signed [18:0] upper=timbre ?
        ($signed(h2)>>>4)+($signed(h3)>>>4)+($signed(h4)>>>5)+
        ($signed(h5)>>>6)+($signed(h6)>>>7) :
        ($signed(h2)>>>4)+($signed(h3)>>>4)+($signed(h4)>>>5)+
        ($signed(h5)>>>5)+($signed(h6)>>>6);
    // Continuous brightness replaces the old abrupt third-harmonic change
    // at velocity=128. Pressure still controls the separate amplitude path.
    wire [7:0] brightness=8'd128+{1'b0,velocity[7:1]};
    wire signed [27:0] bright_product=upper*$signed({1'b0,brightness});
    wire signed [18:0] fundamental=timbre ? ($signed(h1)>>>3) : ($signed(h1)>>>4);
    wire signed [18:0] raw_tone=fundamental+(bright_product>>>8);
    wire signed [18:0] balanced_tone=timbre ? raw_tone-(raw_tone>>>2) : raw_tone;
    wire signed [18:0] body_fast_next=body_fast[index]+((balanced_tone-body_fast[index])>>>1);
    wire signed [18:0] body_slow_next=body_slow[index]+((balanced_tone-body_slow[index])>>>3);
    wire signed [18:0] body_band=body_fast_next-body_slow_next;
    wire signed [19:0] resonant_tone=timbre ?
        balanced_tone+(body_band>>>2) :
        balanced_tone+(body_band>>>1)-(body_slow_next>>>2);

    wire signed [17:0] random_input=$signed(random_state[index][15:0]);
    wire signed [17:0] air_fast_next=air_fast[index]+((random_input-air_fast[index])>>>1);
    wire signed [17:0] air_slow_next=air_slow[index]+((random_input-air_slow[index])>>>3);
    wire signed [18:0] air_band=$signed(air_fast_next)-$signed(air_slow_next);
    wire [5:0] breath_settle=note_age>=16'd4096 ? 6'd0 : (16'd4095-note_age)>>6;
    wire [3:0] friction_grain=phase[31] ? ~phase[30:27] : phase[30:27];
    wire [6:0] texture_gain=timbre ?
        7'd12+{3'd0,velocity[7:4]}+{3'd0,breath_settle[5:2]} :
        7'd16+{3'd0,velocity[7:4]}+{3'd0,friction_grain};
    wire signed [26:0] texture_product=air_band*$signed({1'b0,texture_gain});
    // Air/bow detail must sit behind the pitched tone. The first audition
    // used >>>10 (about 6-8% RMS) and exposed an objectionable steady hiss.
    // Reduce only this additive random component by 24 dB; harmonic colour,
    // body response, onset and pitch expression keep their existing levels.
    wire signed [19:0] combined=resonant_tone+(texture_product>>>14);
    assign wave_out=!active ? 16'sd0 : combined>20'sd32767 ? 16'sh7fff :
        combined< -20'sd32768 ? 16'sh8000 : combined[15:0];

    // Slow, high-resolution filtered randomness; separate state per voice.
    // Bound its influence before it reaches the note-age vibrato envelope.
    wire signed [25:0] wander_input=$signed(random_input)<<<8;
    wire signed [25:0] drift_wide=wander[index]>>>14;
    assign pitch_drift=drift_wide>8 ? 8'sd8 : drift_wide< -8 ? -8'sd8 : drift_wide[7:0];
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            for(i=0;i<VOICES;i=i+1)begin
                random_state[i]<=32'h9e3779b9^(32'h045d9f3b*(i+1));
                air_fast[i]<=0;air_slow[i]<=0;wander[i]<=0;
                body_fast[i]<=0;body_slow[i]<=0;
            end
        end else if(step_en)begin
            random_state[index]<={random_state[index][30:0],
                random_state[index][31]^random_state[index][21]^random_state[index][1]^random_state[index][0]};
            air_fast[index]<=air_fast_next;air_slow[index]<=air_slow_next;
            wander[index]<=wander[index]+((wander_input-wander[index])>>>12);
            body_fast[index]<=active ? body_fast_next : 19'sd0;
            body_slow[index]<=active ? body_slow_next : 19'sd0;
        end
    end
endmodule
