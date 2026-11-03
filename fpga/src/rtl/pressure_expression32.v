// Attack strength stays independent of continuous pressure. Parameters are
// generated from the saved expression profile; no manual boot calibration.
module pressure_expression32 #(
    parameter integer ATTACK_HOLD_FRAMES=1920,
    parameter integer CONTROL_INTERVAL=24,
    parameter integer DEADBAND=3,
    parameter integer SLEW_UP=4,
    parameter integer SLEW_DOWN=2
)(
    input wire clk,rst_n,sample_tick,
    input wire [31:0] gate,remote_owner,
    input wire [95:0] voice_zone,
    input wire [255:0] attack_velocity,
    input wire pressure_valid,
    input wire [2:0] pressure_channel,
    input wire [7:0] pressure_velocity,
    output wire [255:0] performance_velocity,expression
);
    reg [7:0] pad_target[0:6],pad_smooth[0:6];
    localparam integer AGE_BITS=ATTACK_HOLD_FRAMES<1 ? 1 : $clog2(ATTACK_HOLD_FRAMES+1);
    reg [31:0] gate_last;
    reg[31:0] captured_gate,captured_last,captured_remote;
    reg[95:0] captured_zone;
    reg[255:0] captured_attack;
    reg[55:0] captured_pad;
    reg captured_control,scan_busy;
    reg[2:0] scan_group;
    localparam integer COUNT_BITS=CONTROL_INTERVAL<2 ? 1 : $clog2(CONTROL_INTERVAL);
    reg [COUNT_BITS-1:0] control_count;
    wire control_tick=control_count==0;
    integer i;
    function [7:0] approach;
        input [7:0] value,target;
        // Force is eight bits. Keep differences and carries at nine bits,
        // rather than expanding every voice to the integer parameter width.
        reg [8:0] difference,deadband_q;
        localparam [8:0] UP=SLEW_UP>255 ? 255:SLEW_UP;
        localparam [8:0] DOWN=SLEW_DOWN>255 ? 255:SLEW_DOWN;
        localparam [8:0] BAND=DEADBAND>255 ? 255:DEADBAND;
        begin
            // Preserve the noise deadband in the middle of the range, but
            // reach both endpoints exactly, including a slow rise to 255.
            approach=value;difference=0;deadband_q=0;
            if(target>value)begin
                difference={1'b0,target}-{1'b0,value};deadband_q=target==255 ? 0:BAND;
                if(difference>deadband_q)approach=difference>UP ? value+UP:target;
            end else if(value>target)begin
                difference={1'b0,value}-{1'b0,target};deadband_q=target==0 ? 0:BAND;
                if(difference>deadband_q)approach=difference>DOWN ? value-DOWN:target;
            end
        end
    endfunction
    // Four lanes update32 contexts in eight clocks, ahead of the audio
    // renderer's per-voice reads. Capture controls once per sample frame.
    wire[2:0] work_group=sample_tick ? 3'd0:scan_group;
    wire work=sample_tick || scan_busy;
    wire work_control=sample_tick ? control_tick:captured_control;
    genvar lane,g;
    generate for(lane=0;lane<4;lane=lane+1)begin: lanes
        reg[7:0] level[0:7];
        reg[AGE_BITS-1:0] age[0:7];
        wire[4:0] voice_id={work_group,2'b00}+lane;
        wire active=sample_tick ? gate[voice_id]:captured_gate[voice_id];
        wire previous=sample_tick ? gate_last[voice_id]:captured_last[voice_id];
        wire remote=sample_tick ? remote_owner[voice_id]:captured_remote[voice_id];
        wire[2:0] zone=sample_tick ? voice_zone[voice_id*3+:3]:captured_zone[voice_id*3+:3];
        wire[7:0] attack=sample_tick ? attack_velocity[voice_id*8+:8]:captured_attack[voice_id*8+:8];
        wire[7:0] target=sample_tick ? pad_smooth[zone]:captured_pad[zone*8+:8];
        for(g=0;g<8;g=g+1)begin: outputs
            assign performance_velocity[(g*4+lane)*8+:8]=level[g];
            assign expression[(g*4+lane)*8+:8]=level[g];
        end
        integer row;
        always @(posedge clk or negedge rst_n)begin
            if(!rst_n)for(row=0;row<8;row=row+1)begin level[row]<=0;age[row]<=0;end
            else if(work)begin
                if(active && !previous)begin level[work_group]<=attack;age[work_group]<=0;end
                else if(active)begin
                    if(age[work_group]<ATTACK_HOLD_FRAMES)begin age[work_group]<=age[work_group]+1'b1;level[work_group]<=attack;end
                    else if(work_control && !remote && zone<7)level[work_group]<=approach(level[work_group],target);
                end else age[work_group]<=0;
            end
        end
    end endgenerate
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            gate_last<=0;control_count<=0;
            captured_gate<=0;captured_last<=0;captured_remote<=0;captured_zone<=0;captured_attack<=0;captured_pad<=0;
            captured_control<=0;scan_busy<=0;scan_group<=0;
            for(i=0;i<7;i=i+1)begin pad_target[i]<=0;pad_smooth[i]<=0;end
        end else begin
            if(pressure_valid && pressure_channel<7)pad_target[pressure_channel]<=pressure_velocity;
            if(sample_tick)begin
                gate_last<=gate;
                captured_gate<=gate;captured_last<=gate_last;captured_remote<=remote_owner;
                captured_zone<=voice_zone;captured_attack<=attack_velocity;captured_control<=control_tick;
                for(i=0;i<7;i=i+1)captured_pad[i*8+:8]<=pad_smooth[i];
                scan_busy<=1;scan_group<=1;
                control_count<=control_tick ? CONTROL_INTERVAL-1 : control_count-1'b1;
                if(control_tick)for(i=0;i<7;i=i+1)pad_smooth[i]<=approach(pad_smooth[i],pad_target[i]);
            end else if(scan_busy)begin
                if(scan_group==7)scan_busy<=0;else scan_group<=scan_group+1'b1;
            end
        end
    end
endmodule
