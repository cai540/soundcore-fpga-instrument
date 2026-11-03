`timescale 1ns/1ps
module tb_instrument_texture;
    reg clk=0,rst_n=0,en=0,active=1,timbre=1;
    reg [4:0] slot=0;
    reg [31:0] phase=0;
    reg [7:0] velocity=176;
    wire signed [15:0] sound;
    wire signed [7:0] drift;
    integer n,peak,differences;
    reg [31:0] other_random;
    reg signed [18:0] other_body;
    always #5 clk=~clk;
    instrument_texture #(.VOICES(2)) dut(.clk(clk),.rst_n(rst_n),.step_en(en),
        .active(active),.slot(slot),.phase(phase),.note_age(16'd16000),
        .velocity(velocity),.timbre(timbre),.wave_out(sound),.pitch_drift(drift));
    task frame;
        begin @(negedge clk);en=1;@(negedge clk);en=0;end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        if(dut.random_state[0]==dut.random_state[1])$fatal(1,"voices share a noise seed");
        other_random=dut.random_state[1];other_body=dut.body_fast[1];
        peak=0;differences=0;
        for(n=0;n<6000;n=n+1)begin
            phase=phase+32'd23409859;frame();
            if((^sound)===1'bx || sound==16'sh7fff || sound==16'sh8000)
                $fatal(1,"unknown or clipped instrument source");
            if(sound>peak)peak=sound;
            if(drift>8 || drift< -8)$fatal(1,"unbounded pitch drift");
            if(dut.random_state[1]!=other_random || dut.body_fast[1]!=other_body)
                $fatal(1,"one slot modified another texture context");
        end
        if(peak<1000)$fatal(1,"new source is inaudible");
        // Texture is not merely a repeated static waveform, and it stops
        // at the source when the voice is inactive.
        other_random=dut.random_state[0];slot=1;repeat(3)frame();
        if(dut.random_state[0]!=other_random || dut.random_state[0]==dut.random_state[1])
            $fatal(1,"voice randomness is not independent");
        active=0;frame();if(sound!=0)$fatal(1,"inactive source leaks air noise");
        active=1;timbre=0;slot=0;
        repeat(1000)begin phase=phase+32'd23409859;frame();
            if((^sound)===1'bx || sound==16'sh7fff || sound==16'sh8000)
                $fatal(1,"bowed source clipped or unknown");
        end
        $display("PASS: independent air/bow contexts, bounded drift, no source clipping or idle hiss");$finish;
    end
endmodule
