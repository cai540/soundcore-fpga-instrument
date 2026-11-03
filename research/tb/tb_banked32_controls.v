`timescale 1ns/1ps
module tb_banked32_controls;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, enabled=0;
    reg key_up_n=1, key_down_n=1, enc_key_n=1;
    wire [2:0] bank;
    wire sustain_on, clear_pulse;
    integer clears=0;
    banked32_controls #(.DEBOUNCE_CYCLES(2), .LONG_PRESS_CYCLES(12)) dut (
        .clk(clk), .rst_n(rst_n), .enabled(enabled),
        .key_up_n(key_up_n), .key_down_n(key_down_n),
        .enc_key_n(enc_key_n), .bank(bank),
        .sustain_on(sustain_on), .clear_pulse(clear_pulse)
    );
    always @(posedge clk) if (clear_pulse) clears=clears+1;
    task key_up_tap;
        begin
            @(negedge clk); key_up_n=0;
            repeat(8) @(negedge clk);
            key_up_n=1;
            repeat(8) @(negedge clk);
        end
    endtask
    task key_down_tap;
        begin
            @(negedge clk); key_down_n=0;
            repeat(8) @(negedge clk);
            key_down_n=1;
            repeat(8) @(negedge clk);
        end
    endtask
    task enc_short;
        begin
            @(negedge clk); enc_key_n=0;
            repeat(8) @(negedge clk);
            enc_key_n=1;
            repeat(8) @(negedge clk);
        end
    endtask
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        enabled=1;
        repeat(8) @(negedge clk);
        if(bank!==0 || sustain_on!==0) $fatal(1,"bad initial state");
        repeat(5) key_up_tap();
        if(bank!==4) $fatal(1,"bank upper bound %0d",bank);
        key_down_tap();
        if(bank!==3) $fatal(1,"bank decrement %0d",bank);
        enc_short();
        if(!sustain_on) $fatal(1,"short press did not latch sustain");
        @(negedge clk); enc_key_n=0;
        repeat(24) @(negedge clk);
        if(clears!=1 || !sustain_on)
            $fatal(1,"long press clear/sustain error clears=%0d",clears);
        enc_key_n=1;
        repeat(8) @(negedge clk);
        if(clears!=1) $fatal(1,"clear repeated on release");
        enabled=0;
        repeat(3) @(negedge clk);
        if(bank!==0 || sustain_on!==0) $fatal(1,"mode exit did not reset");
        $display("PASS: five bank controls, short sustain, long clear");
        $finish;
    end
endmodule
