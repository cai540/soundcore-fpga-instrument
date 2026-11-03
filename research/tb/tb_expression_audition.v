`timescale 1ns/1ps
module tb_expression_audition;
    reg clk=0,rst_n=0,tick=0,gate=0,timbre=1;always #5 clk=~clk;
    reg [5:0] note=63;wire [31:0] pitch;
    reg [7:0] attack=200,pressure=200;
    wire [255:0] performance,expression;
    wire signed [15:0] old_audio,continuous_audio,new_audio,raw_wave;
    reg signed [15:0] raw_audio;
    wire signed [32:0] raw_envelope=raw_wave*$signed({1'b0,new_voice.envelope});
    wire signed [41:0] raw_product=raw_envelope*$signed({1'b0,performance[7:0]});
    integer kind,frame,local_frame,segment,fo,fc,fr,fn,ft;
    reg [5:0] melody[0:7];
    pressure_expression32 control(.clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate({31'd0,gate}),
        .remote_owner(32'd0),.voice_zone(96'd0),.attack_velocity({248'd0,attack}),
        .pressure_valid(tick),.pressure_channel(3'd0),.pressure_velocity(pressure),
        .performance_velocity(performance),.expression(expression));
    note_step_table35 lookup(.note_index(note),.phase_step(pitch));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) old_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(attack),.timbre(timbre),.sample_out(old_audio));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) continuous_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(performance[7:0]),.timbre(timbre),.sample_out(continuous_audio));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) new_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(pitch),
        .velocity(performance[7:0]),.expression(expression[7:0]),.pitch_index(note),
        .timbre(timbre),.sample_out(new_audio));
    // The uncompensated ablation shares the same oscillator/envelope/pressure
    // context as the normalized voice; only its coefficient bank differs.
    expressive_texture #(.VOICES(1),.NORMALIZE_LEVEL(0)) raw_colour(
        .prepare_en(1'b1),
        .clk(clk),.rst_n(rst_n),.step_en(tick),.active(gate || new_voice.state!=0),
        .slot(5'd0),.phase(new_voice.phase),.note_index(note),.note_age(new_voice.note_age),
        .expression(expression[7:0]),.timbre(new_voice.timbre_latched),.wave_out(raw_wave));
    always @(posedge clk)if(tick)raw_audio<=raw_product[39:24];
    initial begin
        melody[0]=0;melody[1]=2;melody[2]=4;melody[3]=7;
        melody[4]=9;melody[5]=7;melody[6]=4;melody[7]=0;
        fo=$fopen("build/expression_20261028/old.hex","w");
        fc=$fopen("build/expression_20261028/continuous.hex","w");
        fr=$fopen("build/expression_20261028/spectral_raw.hex","w");
        fn=$fopen("build/expression_20261028/spectral_norm.hex","w");
        ft=$fopen("build/expression_20261028/audition_controls.csv","w");
        $fwrite(ft,"timbre,frame,pressure,performance,expression\n");
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
                // Allow synchronous parameter prefetch before the sample tick.
                @(negedge clk);tick=1;@(negedge clk);tick=0;
                if((^new_audio)===1'bx)$fatal(1,"unknown audition sample");
                $fwrite(fo,"%04x\n",old_audio);$fwrite(fc,"%04x\n",continuous_audio);
                $fwrite(fr,"%04x\n",raw_audio);$fwrite(fn,"%04x\n",new_audio);
                if(frame%480==0)$fwrite(ft,"%0d,%0d,%0d,%0d,%0d\n",kind,frame,pressure,performance[7:0],expression[7:0]);
                @(negedge clk);
            end
        end
        $fclose(fo);$fclose(fc);$fclose(fr);$fclose(fn);$fclose(ft);
        $display("PASS:four ablations,576000 actual-RTL single-voice samples each, two timbres, held expression and short melody");$finish;
    end
endmodule
