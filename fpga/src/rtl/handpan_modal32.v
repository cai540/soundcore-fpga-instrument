// Project modal handpan: 32 independently decaying strikes, no sampled audio.
// A single sine table and arithmetic pipeline service 1f/2f/3f resonances.
// Seven clocks per voice = 224 clocks, below a 256-clock 48 kHz frame.
module handpan_modal32 #(
    parameter SINE_FILE="D:/FPGA/Projects/soundcore_2026/rtl/handpan_sine.mem"
) (
    input wire clk,rst_n,sample_tick,enabled,
    input wire strike_valid,
    input wire [6:0] strike_note,
    input wire [7:0] strike_velocity,
    input wire rhythmic,
    input wire [7:0] bend,
    output reg signed [15:0] sample_out,
    output reg sample_valid,
    output reg overflow,
    output wire [5:0] active_count
);
    reg signed [15:0] sine[0:1023];
    initial $readmemh(SINE_FILE,sine);
    reg [31:0] phase[0:31],step[0:31];
    reg [23:0] body[0:31],octave[0:31],fifth[0:31];
    reg [8:0] age[0:31]; // Saturates at256; wider state wastes distributed RAM.
    reg [7:0] strength[0:31];
    reg [31:0] active,short_tail;
    reg [4:0] next_voice,slot;
    reg [6:0] notes[0:7];
    reg [7:0] forces[0:7];
    reg styles[0:7];
    reg [2:0] wr,rd;
    reg [3:0] queued;
    reg busy;
    reg [2:0] stage;
    reg [31:0] read_phase,base_phase;
    reg [15:0] read_envelope,gain_q;
    reg signed [32:0] product;
    reg signed [19:0] resonances;
    reg signed [36:0] gained;
    reg signed [31:0] sum;
    // Allocate at this voice's service slot: all state arrays have one write
    // address, instead of a second asynchronous allocation write port.
    wire pop=enabled && busy && stage==0 && slot==next_voice && !sample_tick && queued!=0;
    wire push=enabled && strike_valid && strike_note<72 && strike_velocity!=0 && (queued<8 || pop);
    wire [31:0] incoming_step;
    note_step_table72 lookup(.note_index(notes[rd]),.phase_step(incoming_step));
    // Metal pitch follows the controller continuously without resetting phase.
    wire signed [8:0] bend_delta=$signed({1'b0,bend})-9'sd128;
    wire signed [41:0] bend_product=$signed({1'b0,step[slot]})*bend_delta;
    wire signed [41:0] bend_scaled=bend_product>>>11;
    wire [31:0] bent_step=step[slot]+bend_scaled[31:0];
    // Prefetch the next resonance in the preceding service stage, allowing
    // a synchronous block ROM without changing the seven-clock voice slot.
    wire[31:0] rom_phase=stage==0 ? (pop ? 32'd0:(active[slot] ? phase[slot]:32'd0)):
        stage==1 ? base_phase*2:stage==2 ? base_phase*3:read_phase;
    reg signed [15:0] wave;
    always @(posedge clk)wave<=sine[rom_phase[31:22]];
    wire signed [31:0] contribution=gained>>>16;
    wire signed [31:0] sum_next=sum+contribution;
    wire signed [31:0] balanced=sum_next>>>1;
    reg [5:0] count;
    integer i;
    always @* begin
        count=0;
        for(integer c=0;c<32;c=c+1)count=count+active[c];
    end
    assign active_count=count;
    function [23:0] decay;
        input [23:0] value;
        input [4:0] shift;
        reg [23:0] decrement;
        begin decrement=value>>shift;decay=value==0 ? 0:value-(decrement==0 ? 24'd1:decrement);end
    endfunction
    // A single synchronous write port; validity is reset independently.
    // Every row is overwritten before becoming active.
    always @(posedge clk)begin
        if(rst_n && enabled && busy && stage==0 && !sample_tick)begin
            if(pop)begin
                phase[slot]<=incoming_step;step[slot]<=incoming_step;
                age[slot]<=1;strength[slot]<=forces[rd];
                body[slot]<=decay(24'd6144000,styles[rd] ? 14:16);
                octave[slot]<=decay((styles[rd] ? 24'd12000+{16'd0,forces[rd]}*24'd16:
                    24'd3000+{16'd0,forces[rd]}*24'd8)<<8,14);
                fifth[slot]<=decay((styles[rd] ? 24'd8000+{16'd0,forces[rd]}*24'd12:
                    24'd600+{16'd0,forces[rd]}*24'd3)<<8,13);
            end else if(active[slot])begin
                phase[slot]<=phase[slot]+(short_tail[slot] ? bent_step:step[slot]);
                if(age[slot]<256)age[slot]<=age[slot]+1'b1;
                body[slot]<=decay(body[slot],short_tail[slot] ? 14:16);
                octave[slot]<=decay(octave[slot],14);
                fifth[slot]<=decay(fifth[slot],13);
            end
        end
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            active<=0;short_tail<=0;next_voice<=0;slot<=0;wr<=0;rd<=0;queued<=0;
            busy<=0;stage<=0;read_phase<=0;base_phase<=0;read_envelope<=0;gain_q<=0;
            product<=0;resonances<=0;gained<=0;sum<=0;sample_out<=0;sample_valid<=0;overflow<=0;
            for(i=0;i<8;i=i+1)begin notes[i]<=0;forces[i]<=0;styles[i]<=0;end
        end else begin
            sample_valid<=0;
            if(!enabled)begin
                active<=0;queued<=0;rd<=0;wr<=0;busy<=0;sample_out<=0;overflow<=0;
            end else begin
                case({push,pop})
                    2'b10:queued<=queued+1'b1;
                    2'b01:queued<=queued-1'b1;
                    default:;
                endcase
                if(strike_valid && !push)overflow<=1;
                if(push)begin notes[wr]<=strike_note;forces[wr]<=strike_velocity;styles[wr]<=rhythmic;wr<=wr+1'b1;end
                if(pop)begin
                    rd<=rd+1'b1;
                    next_voice<=next_voice+1'b1;
                end
                if(sample_tick)begin
                    busy<=1;slot<=0;stage<=0;sum<=0;
                end else if(busy)case(stage)
                    0:begin
                        read_phase<=active[slot] ? phase[slot]:0;base_phase<=active[slot] ? phase[slot]:0;
                        read_envelope<=active[slot] ? body[slot][23:8]:0;
                        gain_q<=active[slot] ? strength[slot]*(short_tail[slot] ?
                            (age[slot]<32 ? {age[slot][4:0],3'd0}:8'd255):
                            (age[slot]<128 ? {age[slot][6:0],1'b0}:8'd255)):0;
                        if(pop)begin
                            // Same first (silent) attack sample and modal state as
                            // an allocation immediately before this audio frame.
                            active[slot]<=1;short_tail[slot]<=styles[rd];
                            read_phase<=0;base_phase<=0;read_envelope<=16'd24000;gain_q<=0;
                        end else if(active[slot])begin
                            if(body[slot]<256)active[slot]<=0;
                        end
                        stage<=1;
                    end
                    1:begin
                        product<=$signed(wave)*$signed({1'b0,read_envelope});
                        read_phase<=base_phase*2;read_envelope<=active[slot] ? octave[slot][23:8]:0;stage<=2;
                    end
                    2:begin
                        resonances<=product>>>16;
                        product<=$signed(wave)*$signed({1'b0,read_envelope});
                        read_phase<=base_phase*3;read_envelope<=active[slot] ? fifth[slot][23:8]:0;stage<=3;
                    end
                    3:begin
                        resonances<=resonances+(product>>>16);
                        product<=$signed(wave)*$signed({1'b0,read_envelope});stage<=4;
                    end
                    4:begin resonances<=resonances+(product>>>16);stage<=5;end
                    5:begin gained<=$signed(resonances)*$signed({1'b0,gain_q});stage<=6;end
                    6:begin
                        sum<=sum_next;
                        if(slot==31)begin
                            sample_out<=balanced>32767 ? 16'sh7fff:balanced< -32768 ? 16'sh8000:balanced[15:0];
                            sample_valid<=1;busy<=0;
                        end else begin slot<=slot+1'b1;stage<=0;end
                    end
                endcase
            end
        end
    end
endmodule

module handpan_pitch_layout(input wire [2:0] bank,pad,input wire [3:0] key,
    output wire [6:0] note_index,output wire valid);
    reg [4:0] interval;
    always @*case(pad)
        0:interval=0;1:interval=2;2:interval=4;3:interval=7;
        4:interval=9;5:interval=12;6:interval=14;default:interval=31;
    endcase
    wire [6:0] requested_root={4'd0,bank}*7'd12+{3'd0,key};
    // Keep the entire voicing in range at the two highest transpositions.
    wire [6:0] root=requested_root>57 ? requested_root-12:requested_root;
    assign note_index=root+{2'd0,interval};
    assign valid=bank<5 && key<12 && pad<7 && note_index<72;
endmodule
