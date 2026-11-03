// Parallel 48 kHz echo, fractional chorus and diffuse reverb.
// Each mix coefficient ramps; their sum stays <= 256 (unity peak bound).
module audio_effects_product (
    input wire clk,rst_n,sample_tick,
    input wire signed [15:0] dry_in,
    input wire [2:0] enable,
    output wire signed [15:0] sample_out
);
    function signed [15:0] clip18;
        input signed [17:0] x;
        begin clip18=x>18'sd32767 ? 16'sh7fff : x< -18'sd32768 ? 16'sh8000 : x[15:0]; end
    endfunction
    function signed [15:0] blend;
        input signed [15:0] a,b;
        input [7:0] amount;
        reg signed [16:0] delta;
        reg signed [25:0] product;
        reg signed [26:0] total;
        begin
            delta=$signed({b[15],b})-$signed({a[15],a});
            product=delta*$signed({1'b0,amount});
            total=$signed({{11{a[15]}},a})+(product>>>8);
            blend=total>27'sd32767 ? 16'sh7fff : total< -27'sd32768 ? 16'sh8000 : total[15:0];
        end
    endfunction
    function signed [15:0] average;
        input signed [15:0] a,b;
        reg signed [16:0] sum;
        begin sum=$signed({a[15],a})+$signed({b[15],b});average=sum>>>1; end
    endfunction
    reg [14:0] warm_count;
    reg [1:0] ramp_div;
    reg [7:0] echo_amount,chorus_amount,room_amount;
    wire [1:0] effect_count={1'b0,enable[0]}+{1'b0,enable[1]}+{1'b0,enable[2]};
    wire [7:0] shared_wet=effect_count==1 ? 8'd96 : effect_count==2 ? 8'd48 : 8'd32;
    wire [7:0] echo_target=enable[0] ? shared_wet : 8'd0;
    wire [7:0] chorus_target=enable[1] ? shared_wet : 8'd0;
    wire [7:0] room_target=enable[2] ? shared_wet : 8'd0;

    // 300 ms echo, bounded 3/4 input + 1/4 feedback.
    reg signed [15:0] echo_mem[0:16383];
    reg [13:0] echo_ptr;
    reg signed [15:0] echo_tap;
    wire [13:0] echo_read_ptr=echo_ptr-14'd14400;
    wire signed [15:0] echo_valid=warm_count>15'd14401 ? echo_tap : 16'sd0;
    wire signed [17:0] echo_input=$signed({{2{dry_in[15]}},dry_in});
    wire signed [17:0] echo_old=$signed({{2{echo_valid[15]}},echo_valid});
    wire signed [17:0] echo_feedback=(echo_input>>>1)+(echo_input>>>2)+(echo_old>>>2);

    // 16 ms +/- 2.67 ms at 0.70 Hz; adjacent samples interpolate the delay.
    reg signed [15:0] chorus_mem_a[0:2047],chorus_mem_b[0:2047];
    reg [10:0] chorus_ptr;
    reg [23:0] chorus_phase;
    wire [15:0] chorus_triangle_u=chorus_phase[23] ?
        {~chorus_phase[22:8],1'b0} : {chorus_phase[22:8],1'b0};
    wire signed [15:0] chorus_triangle=chorus_triangle_u^16'h8000;
    wire signed [19:0] chorus_delay_q8=20'sd196608+
        $signed({{4{chorus_triangle[15]}},chorus_triangle});
    wire [10:0] chorus_delay_integer=chorus_delay_q8[18:8];
    wire [10:0] chorus_read_a=chorus_ptr-chorus_delay_integer;
    wire [10:0] chorus_read_b=chorus_read_a-11'd1;
    reg signed [15:0] chorus_tap_a,chorus_tap_b;
    reg [7:0] chorus_fraction;
    wire signed [15:0] chorus_interpolated=warm_count>15'd2049 ?
        blend(chorus_tap_a,chorus_tap_b,chorus_fraction) : 16'sd0;

    // Four unequal 30..44 ms, low-pass-damped, normalized feedback combs.
    reg signed [15:0] room_a[0:1422],room_b[0:1788];
    reg signed [15:0] room_c[0:1996],room_d[0:2130];
    reg [10:0] room_a_ptr,room_b_ptr,room_c_ptr;
    reg [11:0] room_d_ptr;
    reg signed [15:0] room_a_tap,room_b_tap,room_c_tap,room_d_tap;
    reg signed [15:0] room_a_damped,room_b_damped,room_c_damped,room_d_damped;
    wire signed [15:0] ra=warm_count>15'd1424 ? room_a_tap : 16'sd0;
    wire signed [15:0] rb=warm_count>15'd1790 ? room_b_tap : 16'sd0;
    wire signed [15:0] rc=warm_count>15'd1998 ? room_c_tap : 16'sd0;
    wire signed [15:0] rd=warm_count>15'd2132 ? room_d_tap : 16'sd0;
    wire signed [17:0] room_input=$signed({{2{dry_in[15]}},dry_in});
    wire signed [17:0] ra_feedback=$signed({{2{room_a_damped[15]}},room_a_damped});
    wire signed [17:0] rb_feedback=$signed({{2{room_b_damped[15]}},room_b_damped});
    wire signed [17:0] rc_feedback=$signed({{2{room_c_damped[15]}},room_c_damped});
    wire signed [17:0] rd_feedback=$signed({{2{room_d_damped[15]}},room_d_damped});
    wire signed [17:0] room_sum=$signed({{2{ra[15]}},ra})+
        $signed({{2{rb[15]}},rb})+$signed({{2{rc[15]}},rc})+$signed({{2{rd[15]}},rd});
    wire signed [15:0] room_average=room_sum>>>2;
    wire [9:0] wet_total={2'b0,echo_amount}+{2'b0,chorus_amount}+{2'b0,room_amount};
    wire [9:0] dry_amount=10'd256-wet_total;
    wire signed [26:0] dry_product=dry_in*$signed({1'b0,dry_amount});
    wire signed [24:0] echo_product=echo_valid*$signed({1'b0,echo_amount});
    wire signed [24:0] chorus_product=chorus_interpolated*$signed({1'b0,chorus_amount});
    wire signed [24:0] room_product=room_average*$signed({1'b0,room_amount});
    wire signed [28:0] output_sum=$signed(dry_product)+$signed(echo_product)+
        $signed(chorus_product)+$signed(room_product);
    assign sample_out=output_sum>>>8;

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            warm_count<=0;ramp_div<=0;
            echo_amount<=0;chorus_amount<=0;room_amount<=0;
            echo_ptr<=0;echo_tap<=0;
            chorus_ptr<=0;chorus_phase<=0;chorus_tap_a<=0;chorus_tap_b<=0;chorus_fraction<=0;
            room_a_ptr<=0;room_b_ptr<=0;room_c_ptr<=0;room_d_ptr<=0;
            room_a_tap<=0;room_b_tap<=0;room_c_tap<=0;room_d_tap<=0;
            room_a_damped<=0;room_b_damped<=0;room_c_damped<=0;room_d_damped<=0;
        end else if(sample_tick)begin
            if(warm_count!=15'd32767)warm_count<=warm_count+1'b1;
            ramp_div<=ramp_div+1'b1;
            if(ramp_div==0)begin
                if(echo_amount<echo_target)echo_amount<=echo_amount+1'b1;
                else if(echo_amount>echo_target)echo_amount<=echo_amount-1'b1;
                if(chorus_amount<chorus_target)chorus_amount<=chorus_amount+1'b1;
                else if(chorus_amount>chorus_target)chorus_amount<=chorus_amount-1'b1;
                if(room_amount<room_target)room_amount<=room_amount+1'b1;
                else if(room_amount>room_target)room_amount<=room_amount-1'b1;
            end
            echo_tap<=echo_mem[echo_read_ptr];
            echo_mem[echo_ptr]<=clip18(echo_feedback);
            echo_ptr<=echo_ptr+1'b1;
            chorus_tap_a<=chorus_mem_a[chorus_read_a];
            chorus_tap_b<=chorus_mem_b[chorus_read_b];
            chorus_fraction<=chorus_delay_q8[7:0];
            chorus_mem_a[chorus_ptr]<=dry_in;
            chorus_mem_b[chorus_ptr]<=dry_in;
            chorus_ptr<=chorus_ptr+1'b1;
            chorus_phase<=chorus_phase+24'd245;
            room_a_tap<=room_a[room_a_ptr];room_b_tap<=room_b[room_b_ptr];
            room_c_tap<=room_c[room_c_ptr];room_d_tap<=room_d[room_d_ptr];
            room_a_damped<=average(ra,room_a_damped);
            room_b_damped<=average(rb,room_b_damped);
            room_c_damped<=average(rc,room_c_damped);
            room_d_damped<=average(rd,room_d_damped);
            room_a[room_a_ptr]<=clip18((room_input>>>2)+(ra_feedback>>>1)+(ra_feedback>>>2));
            room_b[room_b_ptr]<=clip18((room_input>>>2)+(rb_feedback>>>1)+(rb_feedback>>>2));
            room_c[room_c_ptr]<=clip18((room_input>>>2)+(rc_feedback>>>1)+(rc_feedback>>>2));
            room_d[room_d_ptr]<=clip18((room_input>>>2)+(rd_feedback>>>1)+(rd_feedback>>>2));
            room_a_ptr<=room_a_ptr==11'd1422 ? 0 : room_a_ptr+1'b1;
            room_b_ptr<=room_b_ptr==11'd1788 ? 0 : room_b_ptr+1'b1;
            room_c_ptr<=room_c_ptr==11'd1996 ? 0 : room_c_ptr+1'b1;
            room_d_ptr<=room_d_ptr==12'd2130 ? 0 : room_d_ptr+1'b1;
        end
    end
endmodule

