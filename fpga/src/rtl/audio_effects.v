// Three independently selectable, low-cost 48 kHz effects. The memories are
// updated once per audio sample; dry audio is always present. Bit 0: echo,
// bit 1: short modulated chorus, bit 2: two-comb reverb.
module audio_effects (
    input wire clk,
    input wire rst_n,
    input wire sample_tick,
    input wire signed [15:0] dry_in,
    input wire [2:0] enable,
    output wire signed [15:0] sample_out
);
    reg signed [15:0] echo_mem [0:8191];
    reg signed [15:0] chorus_mem [0:255];
    reg signed [15:0] room_a [0:1022];
    reg signed [15:0] room_b [0:766];
    reg [12:0] echo_ptr;
    reg [7:0] chorus_ptr;
    reg [9:0] room_a_ptr, room_b_ptr;
    reg signed [15:0] echo_tap, chorus_tap, room_a_tap, room_b_tap;
    reg [7:0] lfo;
    reg [8:0] lfo_div;
    reg [13:0] warm_count;
    wire [7:0] chorus_offset = 8'd86 + (lfo[7] ? ~lfo[6:0] : lfo[6:0]);
    wire [7:0] chorus_read_ptr = chorus_ptr - chorus_offset;
    wire signed [17:0] echo_feedback =
        $signed({{2{dry_in[15]}},dry_in}) +
        (enable[0] && warm_count > 14'd8192 ?
         ($signed({{2{echo_tap[15]}},echo_tap}) >>> 2) : 18'sd0);
    function signed [15:0] clip18;
        input signed [17:0] x;
        begin
            clip18 = x > 18'sd32767 ? 16'sh7fff :
                     x < -18'sd32768 ? 16'sh8000 : x[15:0];
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            echo_ptr <= 0;
            chorus_ptr <= 0;
            room_a_ptr <= 0;
            room_b_ptr <= 0;
            echo_tap <= 0;
            chorus_tap <= 0;
            room_a_tap <= 0;
            room_b_tap <= 0;
            lfo <= 0;
            lfo_div <= 0;
            warm_count <= 0;
        end else if (sample_tick) begin
            if (warm_count < 14'd8193) warm_count <= warm_count + 1'b1;
            echo_tap <= echo_mem[echo_ptr];
            echo_mem[echo_ptr] <= clip18(echo_feedback);
            echo_ptr <= echo_ptr + 1'b1;

            chorus_tap <= chorus_mem[chorus_read_ptr];
            chorus_mem[chorus_ptr] <= dry_in;
            chorus_ptr <= chorus_ptr + 1'b1;
            if (lfo_div == 9'd187) begin
                lfo_div <= 0;
                lfo <= lfo + 1'b1;
            end else lfo_div <= lfo_div + 1'b1;

            room_a_tap <= room_a[room_a_ptr];
            room_a[room_a_ptr] <= (dry_in >>> 1) +
                (enable[2] && warm_count > 14'd1023 ?
                 (room_a_tap >>> 1) : 16'sd0);
            room_a_ptr <= room_a_ptr == 10'd1022 ? 0 : room_a_ptr + 1'b1;
            room_b_tap <= room_b[room_b_ptr];
            room_b[room_b_ptr] <= (dry_in >>> 1) +
                (enable[2] && warm_count > 14'd767 ?
                 (room_b_tap >>> 1) : 16'sd0);
            room_b_ptr <= room_b_ptr == 10'd766 ? 0 : room_b_ptr + 1'b1;
        end
    end

    wire signed [19:0] dry = {{4{dry_in[15]}},dry_in};
    wire [1:0] enabled_count = {1'b0,enable[0]} +
                               {1'b0,enable[1]} + {1'b0,enable[2]};
    wire signed [19:0] dry_mix = enabled_count == 2'd0 ? dry :
                                 enabled_count == 2'd1 ?
                                 (enable[1] ? (dry >>> 1) :
                                  (dry - (dry >>> 2))) :
                                 enabled_count == 2'd2 ? (dry >>> 1) :
                                 (dry >>> 2);
    wire multiple_effects = enabled_count >= 2;
    wire signed [19:0] wet_echo = enable[0] && warm_count > 14'd8192 ?
        ($signed({{4{echo_tap[15]}},echo_tap}) >>>
         (multiple_effects ? 3 : 2)) : 20'sd0;
    // A 50/50 delayed blend is audible as chorus at the speaker. Cut its
    // share when combined with another effect so the bus keeps headroom.
    wire signed [19:0] wet_chorus = enable[1] && warm_count > 14'd256 ?
        ($signed({{4{chorus_tap[15]}},chorus_tap}) >>>
         (multiple_effects ? 2 : 1)) : 20'sd0;
    wire signed [19:0] wet_room =
        (enable[2] && warm_count > 14'd1023 ?
         ($signed({{4{room_a_tap[15]}},room_a_tap}) >>>
          (multiple_effects ? 4 : 3)) : 20'sd0) +
        (enable[2] && warm_count > 14'd767 ?
         ($signed({{4{room_b_tap[15]}},room_b_tap}) >>>
          (multiple_effects ? 4 : 3)) : 20'sd0);
    wire signed [19:0] mixed = dry_mix + wet_echo + wet_chorus + wet_room;
    assign sample_out = mixed > 20'sd32767 ? 16'sh7fff :
                        mixed < -20'sd32768 ? 16'sh8000 : mixed[15:0];
endmodule
