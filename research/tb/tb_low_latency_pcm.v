`timescale 1ns/1ps
// Compare actual expressive RTL against frozen 7B69, not a sine-wave model.
module tb_low_latency_pcm;
    reg clk=0,rst_n=0,tick=0,gate=0,timbre=0;
    reg [31:0] step=23409859;
    reg [6:0] pitch=24;
    reg [7:0] level=176;
    always #5 clk=~clk;
    wire signed [15:0] live,old_live,song,old_song;
    wire valid,old_valid;
    integer kind,key,vel,n,checks=0;
    poly_synth32_tm #(.EXPRESSION_TEXTURE(1)) a(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate({31'd0,gate}),
        .phase_step({992'd0,step}),.velocity({248'd0,level}),.expression({248'd0,level}),
        .pitch_index({217'd0,pitch}),.timbre(timbre),.sample_out(live),.sample_valid(valid));
    reference_poly_synth32_tm #(.EXPRESSION_TEXTURE(1)) b(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate({31'd0,gate}),
        .phase_step({992'd0,step}),.velocity({248'd0,level}),.expression({248'd0,level}),
        .pitch_index({217'd0,pitch}),.timbre(timbre),.sample_out(old_live),.sample_valid(old_valid));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) c(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(step),
        .velocity(level),.expression(level),.pitch_index(pitch),.timbre(timbre),.sample_out(song));
    reference_synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1),.EXPRESSION_TEXTURE(1)) d(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),.phase_step(step),
        .velocity(level),.expression(level),.pitch_index(pitch),.timbre(timbre),.sample_out(old_song));
    task frame;
        begin
            @(negedge clk);tick=1;@(negedge clk);tick=0;
            repeat(254)@(negedge clk);
            if((^live)===1'bx || (^song)===1'bx)$fatal(1,"unknown PCM");
        end
    endtask
    initial begin
        for(kind=0;kind<2;kind=kind+1)for(key=0;key<3;key=key+1)for(vel=0;vel<2;vel=vel+1)begin
            rst_n=0;gate=0;timbre=kind;level=vel ? 220:72;
            case(key)
                0:begin pitch=0;step=5852465;end
                1:begin pitch=24;step=23409859;end
                2:begin pitch=48;step=93639436;end
            endcase
            repeat(3)@(negedge clk);rst_n=1;frame();gate=1;
            for(n=0;n<800;n=n+1)begin
                frame();
                if(n>=520)begin
                    checks=checks+1;
                    if(live!==old_live || song!==old_song)
                        $fatal(1,"steady PCM changed timbre=%0d key=%0d level=%0d frame=%0d",kind,key,level,n);
                end
            end
            gate=0;
            repeat(100)begin frame();checks=checks+1;
                if(live!==old_live || song!==old_song)$fatal(1,"release PCM changed");
            end
        end
        $display("PASS: %0d actual expressive PCM comparisons: live/offline, both timbres, C2/C4/C6, soft/strong, sustained and release bit-identical to 7B69",checks);
        $finish;
    end
endmodule
