`timescale 1ns/1ps
module tb_timbre_repair_audition;
    reg clk=0,rst_n=0,tick=0,gate=0,timbre=1;always #5 clk=~clk;
    reg [5:0] note=63;wire [31:0] pitch;
    reg [7:0] attack=200,pressure=200;
    wire [255:0] performance,expression;
    wire signed [15:0] before_audio,after_audio,tonal_audio;
    integer kind,frame,local_frame,segment,fo,fn,ft;
    reg [5:0] melody[0:7];
    pressure_expression32 control(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate({31'd0,gate}),
        .remote_owner(32'd0),.voice_zone(96'd0),.attack_velocity({248'd0,attack}),
        .pressure_valid(tick),.pressure_channel(3'd0),.pressure_velocity(pressure),
        .performance_velocity(performance),.expression(expression));
    note_step_table35 lookup(.note_index(note),.phase_step(pitch));
    repair_old_synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) old_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(performance[7:0]),.expression(expression[7:0]),.pitch_index(note),.timbre(timbre),.sample_out(before_audio));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) new_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(performance[7:0]),.expression(expression[7:0]),.pitch_index(note),.timbre(timbre),.sample_out(after_audio));
    repair_tonal_synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) tonal_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(performance[7:0]),.expression(expression[7:0]),.pitch_index(note),.timbre(timbre),.sample_out(tonal_audio));
    initial begin
        melody[0]=0;melody[1]=2;melody[2]=4;melody[3]=7;
        melody[4]=9;melody[5]=7;melody[6]=4;melody[7]=0;
        fo=$fopen("build/timbre_pressure_repair_20261101/before.hex","w");
        fn=$fopen("build/timbre_pressure_repair_20261101/after.hex","w");
        ft=$fopen("build/timbre_pressure_repair_20261101/tonal.hex","w");
        for(kind=0;kind<2;kind=kind+1)begin
            rst_n=0;tick=0;gate=0;timbre=kind==0;
            repeat(3)@(negedge clk);rst_n=1;
            for(frame=0;frame<288000;frame=frame+1)begin
                if(frame<144000)begin
                    note=12;attack=200;gate=frame>=4800 && frame<134400;
                    pressure=frame<28800 ? 200 : frame<67200 ? 55 : frame<105600 ? 235 : 70;
                end else begin
                    local_frame=frame-144000;segment=local_frame/18000;note=melody[segment];
                    attack=140+(segment%3)*25;pressure=attack;gate=local_frame%18000<14500;
                end
                @(negedge clk);tick=1;@(negedge clk);tick=0;
                if((^after_audio)===1'bx || (^before_audio)===1'bx)$fatal(1,"unknown audition sample");
                $fwrite(fo,"%04x\n",before_audio);$fwrite(fn,"%04x\n",after_audio);$fwrite(ft,"%04x\n",tonal_audio);
                @(negedge clk);
            end
        end
        $fclose(fo);$fclose(fn);$fclose(ft);
        $display("PASS:576000 actual RTL samples per variant, old/current candidate/tonal control, both instruments");$finish;
    end
endmodule
