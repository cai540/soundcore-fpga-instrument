`timescale 1ns/1ps
module tb_early_pressure_allocator;
    reg clk=0,rst_n=0,valid=0;
    always #5 clk=~clk;
    reg [3:0] frame=0;
    always @(posedge clk)frame<=frame+1'b1;
    wire tick=frame==0;
    reg [2:0] ch=0;
    reg [11:0] adc=1000;
    wire fire,early,lv;
    wire [2:0] pad,lp;
    wire [7:0] velocity,level;
    wire [6:0] pressed;
    wire [31:0] gate;
    wire [255:0] voice_velocity;
    wire [191:0] notes;
    integer step,j,k,count,events=0,owners[0:6];
    fsr_strike_detector #(.EARLY_ENABLE(1),.CAL_SAMPLES(2),.REARM_SAMPLES(3)) detector(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(adc),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(velocity),.strike_early(early),
        .level_valid(lv),.level_channel(lp),.level_velocity(level),.pressed(pressed));
    strike_voice_allocator32 #(.BANKED_MODE(1),.HOLD_SAMPLES(2),.RELEASE_SAMPLES(2)) allocator(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.strike_valid(fire),.strike_channel(pad),
        .strike_velocity(velocity),.level_valid(lv),.level_channel(lp),.level_velocity(level),
        .pressed(pressed),.remote_strike_valid(1'b0),.remote_strike_channel(3'd0),
        .remote_strike_velocity(8'd0),.remote_pressed(7'd0),.bank(3'd4),.banked_enable(1'b1),
        .sustain(1'b0),.clear_all(1'b0),.gate(gate),.note_index(notes),.velocity(voice_velocity));
    always @(posedge clk) if(rst_n && fire)events=events+1;
    task put;
        input integer channel;
        input integer value;
        begin
            @(negedge clk);ch=channel;adc=value;valid=1;
            @(negedge clk);valid=0;repeat(31)@(negedge clk);
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        for(j=0;j<7;j=j+1)begin put(j,1000);put(j,1000);end
        for(step=0;step<5;step=step+1)begin
            // Late stronger peak after provisional plateau: same voice is corrected.
            for(j=0;j<7;j=j+1)put(j,step<3 ? 1600 : (step==3 ? 2100 : 2050));
            if(step==2)begin
                count=0;
                for(k=0;k<32;k=k+1)if(gate[k])begin
                    count=count+1;owners[notes[k*6 +: 6]-28]=k;
                    if(voice_velocity[k*8 +: 8]!=30)$fatal(1,"wrong provisional velocity");
                end
                if(count!=7 || events!=7)$fatal(1,"early chord missing/duplicate notes");
            end
        end
        for(j=0;j<7;j=j+1)begin
            k=owners[j];
            if(!gate[k] || notes[k*6 +: 6]!=28+j || voice_velocity[k*8 +: 8]!=212)
                $fatal(1,"late peak did not correct existing owner pad=%0d vel=%0d",j,voice_velocity[k*8 +: 8]);
        end
        if(events!=7)$fatal(1,"correction created another attack");
        // Releasing one physical pad must preserve all six other owners.
        for(step=0;step<5;step=step+1)put(3,1000);
        repeat(40)@(negedge clk);
        for(j=0;j<7;j=j+1)if(gate[owners[j]]!==(j!=3))$fatal(1,"release damaged unrelated chord pad=%0d",j);
        $display("PASS: seven early voices corrected30->212 in original slots, no second NOTE_ON, independent single-pad release");
        $finish;
    end
endmodule
