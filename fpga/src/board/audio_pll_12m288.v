// GW5AT-60 PLLA candidate for the standalone external-DAC diagnostic.
// Nominal: 50 MHz / 2 * 29 = 725 MHz VCO;
//          725 MHz / 59 = 12.2881356 MHz (about +11 ppm from 12.288 MHz).
// This is not a measured clock. Confirm place/route timing and LRCLK on board.
module audio_pll_12m288 (
    input  wire clkin,
    output wire clk_audio,
    output wire locked
);
    wire gnd = 1'b0;
    wire [6:1] unused_clkout;
    wire unused_clkfbout;
    wire [7:0] unused_mdrdo;
    PLLA #(
        .FCLKIN("50"),
        .IDIV_SEL(2),
        .FBDIV_SEL(1),
        .MDIV_SEL(29),
        .MDIV_FRAC_SEL(0),
        .ODIV0_SEL(59),
        .ODIV0_FRAC_SEL(0),
        .CLKOUT0_EN("TRUE"),
        .CLKOUT1_EN("FALSE"),
        .CLKOUT2_EN("FALSE"),
        .CLKOUT3_EN("FALSE"),
        .CLKOUT4_EN("FALSE"),
        .CLKOUT5_EN("FALSE"),
        .CLKOUT6_EN("FALSE"),
        .CLKFB_SEL("INTERNAL")
    ) pll (
        .CLKIN(clkin), .CLKFB(gnd), .CLKOUT0(clk_audio), .LOCK(locked),
        .CLKOUT1(unused_clkout[1]), .CLKOUT2(unused_clkout[2]),
        .CLKOUT3(unused_clkout[3]), .CLKOUT4(unused_clkout[4]),
        .CLKOUT5(unused_clkout[5]), .CLKOUT6(unused_clkout[6]),
        .CLKFBOUT(unused_clkfbout), .MDRDO(unused_mdrdo),
        .RESET(gnd), .PLLPWD(gnd), .RESET_I(gnd), .RESET_O(gnd),
        .PSSEL(3'b0), .PSDIR(gnd), .PSPULSE(gnd),
        .SSCPOL(gnd), .SSCON(gnd), .SSCMDSEL(7'b0),
        .SSCMDSEL_FRAC(3'b0),
        .MDCLK(gnd), .MDOPC(2'b0), .MDAINC(gnd), .MDWDI(8'b0)
    );
endmodule
