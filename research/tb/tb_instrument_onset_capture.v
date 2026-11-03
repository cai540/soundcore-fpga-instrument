`timescale 1ns/1ps
// Capture real RTL, including the shared 32-voice path, rather than a Python
// approximation of the sound. Both outputs receive the same note events.
module tb_instrument_onset_capture;
    reg clk=0,rst_n=0,tick=0,gate=0,timbre=1;
    reg [31:0] step=32'd23409859;
    reg [7:0] velocity=176;
    wire signed [15:0] manual_sample,song_sample;
    wire valid;
    integer n,local_n,segment,fd,unused;
    reg [2047:0] output_path;
    always #5 clk=~clk;
    poly_synth32_tm manual_voice(.clk(clk),.rst_n(rst_n),.sample_tick(tick),
        .gate({31'd0,gate}),.phase_step({992'd0,step}),
        .velocity({248'd0,velocity}),.timbre(timbre),
        .sample_out(manual_sample),.sample_valid(valid));
    synth_voice #(.INSTRUMENT_PRESETS(1),.NATURAL_VIBRATO(1)) song_voice(
        .clk(clk),.rst_n(rst_n),.sample_tick(tick),.gate(gate),
        .phase_step(step),.velocity(velocity),.timbre(timbre),.sample_out(song_sample));
    initial begin
        output_path="build/onset_20261027/capture.hex";
        unused=$value$plusargs("OUT=%s",output_path);
        fd=$fopen(output_path,"w");if(!fd)$fatal(1,"capture file cannot open");
        repeat(3)@(negedge clk);rst_n=1;
        for(n=0;n<240000;n=n+1)begin
            // 2.5 seconds each: soft note, strong note, then rapid repeats.
            timbre=(n<120000);local_n=n%120000;
            gate=(local_n>=4800 && local_n<24000) ||
                 (local_n>=43200 && local_n<72000) ||
                 (local_n>=91200 && local_n<115200 && (local_n%4800)<2400);
            velocity=local_n<43200 ? 8'd72 : 8'd220;
            step=local_n<91200 ? 32'd23409859 : 32'd35074619;
            @(negedge clk);tick=1;@(negedge clk);tick=0;
            repeat(200)@(negedge clk);
            if((^manual_sample)===1'bx || (^song_sample)===1'bx)
                $fatal(1,"unknown captured sample %0d",n);
            $fdisplay(fd,"%04x %04x %0d %0d",manual_sample,song_sample,
                manual_voice.envelope[0],song_voice.envelope);
        end
        $fclose(fd);$display("PASS: actual 32-voice and offline onsets captured");$finish;
    end
endmodule
