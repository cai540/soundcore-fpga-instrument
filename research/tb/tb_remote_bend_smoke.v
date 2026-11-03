`timescale 1ns/1ps
module tb_remote_bend_smoke;
    reg clk=0,rst_n=0,command_valid=0,session=1;
    reg [7:0] command_type=0,command_value=0;
    wire adc_cs_n,adc_sclk,adc_mosi,adc_miso;
    wire dac_bclk,dac_lrclk,dac_din;
    wire [7:0] bend;
    integer i;
    wire [11:0] mock_sample=12'd2048;
    always #5 clk=~clk;
    pressure_i2s_additive32_core #(.PANEL_CONTROL(1),.BANKED32_AVAILABLE(1),
        .SCAN_HALF_CYCLES(2),.SCAN_GAP_CYCLES(2),.CAL_SAMPLES(2)) dut (
        .clk_audio(clk),.rst_n(rst_n),.adc_cs_n(adc_cs_n),
        .adc_sclk(adc_sclk),.adc_mosi(adc_mosi),.adc_miso(adc_miso),
        .enc_s1_n(1'b1),.enc_s2_n(1'b1),.enc_key_n(1'b1),
        .key_up_n(1'b1),.key_down_n(1'b1),.panel_bank(3'd0),
        .panel_timbre(1'b1),.panel_vibrato_enabled(1'b0),
        .panel_vibrato_depth(4'd0),.panel_volume_level(5'd16),
        .panel_effect_mask(3'd0),
        .remote_command_valid(command_valid),.remote_command_type(command_type),
        .remote_command_value(command_value),.remote_session_active(session),
        .remote_strike_valid(1'b0),.remote_strike_channel(3'd0),
        .remote_strike_velocity(8'd0),.remote_pressed(7'd0),
        .bend_o(bend),.dac_bclk(dac_bclk),.dac_lrclk(dac_lrclk),.dac_din(dac_din)
    );
    assign adc_miso = dut.scanner.bit_index <= 11 ?
        mock_sample[dut.scanner.bit_index] : 1'b0;
    task send;
        input [7:0] typ,val;
        begin
            @(negedge clk);command_type=typ;command_value=val;command_valid=1;
            @(negedge clk);command_valid=0;
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;
        repeat(20000)@(negedge clk);
        send(8'h1b,8'd220);
        repeat(50000)@(negedge clk);
        if(bend<200 || bend>220)$fatal(1,"remote bend did not take effect: %0d",bend);
        send(8'h1c,0);
        repeat(50000)@(negedge clk);
        if(bend<120 || bend>136)$fatal(1,"release did not return to slider: %0d",bend);
        send(8'h1b,8'd20);
        repeat(50000)@(negedge clk);
        session=0;
        repeat(50000)@(negedge clk);
        if(bend<120 || bend>136)$fatal(1,"session revoke left bend active: %0d",bend);
        $display("PASS: temporary bend, smooth release and session revoke");
        $finish;
    end
endmodule
