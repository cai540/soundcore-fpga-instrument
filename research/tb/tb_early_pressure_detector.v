`timescale 1ns/1ps
module tb_early_pressure_detector;
    reg clk=0,rst_n=0,valid=0;
    reg [2:0] ch=0;
    reg [11:0] value=1000;
    always #5 clk=~clk;
    wire fire,old_fire,early,level;
    wire [2:0] pad,old_pad,level_pad;
    wire [7:0] vel,old_vel,level_vel;
    wire [6:0] pressed;
    integer early_count[0:6],old_count[0:6],early_at[0:6],old_at[0:6];
    integer first_velocity[0:6],last_velocity[0:6],final_level[0:6],tag_count[0:6];
    integer i,j,kind,target,step=0,cases=0,early_cases=0;
    reg [6:0] mask;
    reg [11:0] excursion[0:4];
    fsr_strike_detector #(.EARLY_ENABLE(1),.CAL_SAMPLES(2),.PEAK_SAMPLES(4),.REARM_SAMPLES(3)) dut(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(value),
        .strike_valid(fire),.strike_channel(pad),.strike_velocity(vel),.level_valid(level),
        .level_channel(level_pad),.level_velocity(level_vel),.pressed(pressed),.strike_early(early));
    fsr_strike_detector_legacy #(.CAL_SAMPLES(2),.PEAK_SAMPLES(4),.REARM_SAMPLES(3)) reference(
        .clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample_channel(ch),.sample_value(value),
        .strike_valid(old_fire),.strike_channel(old_pad),.strike_velocity(old_vel));
    always @(posedge clk)begin
        #1;
        if(rst_n)begin
            if(fire)begin
                early_count[pad]=early_count[pad]+1;early_at[pad]=step;
                first_velocity[pad]=vel;if(early)tag_count[pad]=tag_count[pad]+1;
            end
            if(old_fire)begin old_count[old_pad]=old_count[old_pad]+1;old_at[old_pad]=step;last_velocity[old_pad]=old_vel;end
            if(level)final_level[level_pad]=level_vel;
        end
    end
    task put;
        input integer channel;
        input integer adc;
        begin @(negedge clk);ch=channel;value=adc;valid=1;@(negedge clk);valid=0;end
    endtask
    task reset;
        begin
            rst_n=0;valid=0;repeat(3)@(negedge clk);
            for(i=0;i<7;i=i+1)begin
                early_count[i]=0;old_count[i]=0;early_at[i]=-1;old_at[i]=-1;
                first_velocity[i]=0;last_velocity[i]=0;final_level[i]=0;tag_count[i]=0;
            end
            rst_n=1;
            for(i=0;i<7;i=i+1)begin put(i,1000);put(i,1000);end
        end
    endtask
    initial begin
        for(kind=0;kind<6;kind=kind+1)begin
            case(kind)
                0:begin excursion[0]=800;excursion[1]=800;excursion[2]=800;excursion[3]=800;excursion[4]=800;end
                1:begin excursion[0]=300;excursion[1]=450;excursion[2]=650;excursion[3]=850;excursion[4]=1050;end
                2:begin excursion[0]=900;excursion[1]=880;excursion[2]=860;excursion[3]=840;excursion[4]=820;end
                3:begin excursion[0]=900;excursion[1]=0;excursion[2]=0;excursion[3]=0;excursion[4]=0;end
                4:begin excursion[0]=600;excursion[1]=600;excursion[2]=600;excursion[3]=1100;excursion[4]=1050;end
                5:begin excursion[0]=300;excursion[1]=300;excursion[2]=300;excursion[3]=300;excursion[4]=300;end
            endcase
            for(target=0;target<8;target=target+1)begin
                reset();mask=target==7 ? 7'h7f : 7'd1<<target;
                for(step=0;step<5;step=step+1)for(j=0;j<7;j=j+1)put(j,1000+(mask[j] ? excursion[step] : 0));
                @(negedge clk);
                for(j=0;j<7;j=j+1)begin
                    if(mask[j])begin
                        if(early_count[j]!=1 || old_count[j]!=1)$fatal(1,"missing/duplicate event kind=%0d pad=%0d",kind,j);
                        if(kind==0 || kind==2 || kind==4)begin
                            if(early_at[j]!=2 || old_at[j]!=4 || tag_count[j]!=1)$fatal(1,"early commit timing wrong");
                            early_cases=early_cases+1;
                        end else if(early_at[j]!=4 || tag_count[j]!=0)$fatal(1,"uncertain waveform must use legacy timing");
                        if(kind!=4 && first_velocity[j]!=last_velocity[j])$fatal(1,"provisional peak differs on settled case");
                        if(kind==4 && (first_velocity[j]>=last_velocity[j] || final_level[j]!=last_velocity[j]))
                            $fatal(1,"late peak did not correct same-note level");
                    end else if(early_count[j] || old_count[j])$fatal(1,"quiet neighbour triggered");
                end
                // Held observations must not retrigger. All release independently.
                step=5;for(i=0;i<6;i=i+1)for(j=0;j<7;j=j+1)put(j,1000);
                if(pressed!==0)$fatal(1,"pads did not rearm");
                for(j=0;j<7;j=j+1)if(early_count[j]!=(mask[j]?1:0))$fatal(1,"duplicate on release");
                cases=cases+1;
            end
        end
        // Neither idle noise nor initial baseline acquisition needs a user action.
        reset();for(i=0;i<20;i=i+1)for(j=0;j<7;j=j+1)put(j,1000+(i%3)*10);
        for(j=0;j<7;j=j+1)if(early_count[j])$fatal(1,"idle noise triggered");
        $display("PASS: %0d synthetic traces; %0d pad events early at2 vs4 follow samples; slow/noisy/low-margin fallback, seven-pad chords, one-shot and final peak correction",cases,early_cases);
        $finish;
    end
endmodule
