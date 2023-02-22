//Copyright (C)2014-2022 Gowin Semiconductor Corporation.
//All rights reserved.
//File Title: IP file
//GOWIN Version: V1.9.8.05
//Part Number: GW1NR-LV9QN88PC6/I5
//Device: GW1NR-9C
//Created Time: Sat Feb 18 19:49:19 2023

module SRAM (dout, clk, oce, ce, reset, wre, ad, din);

output [8:0] dout;
input clk;
input oce;
input ce;
input reset;
input wre;
input [6:0] ad;
input [8:0] din;

wire [26:0] spx9_inst_0_dout_w;
wire gw_gnd;

assign gw_gnd = 1'b0;

SPX9 spx9_inst_0 (
    .DO({spx9_inst_0_dout_w[26:0],dout[8:0]}),
    .CLK(clk),
    .OCE(oce),
    .CE(ce),
    .RESET(reset),
    .WRE(wre),
    .BLKSEL({gw_gnd,gw_gnd,gw_gnd}),
    .AD({gw_gnd,gw_gnd,gw_gnd,gw_gnd,ad[6:0],gw_gnd,gw_gnd,gw_gnd}),
    .DI({gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,din[8:0]})
);

defparam spx9_inst_0.READ_MODE = 1'b0;
defparam spx9_inst_0.WRITE_MODE = 2'b00;
defparam spx9_inst_0.BIT_WIDTH = 9;
defparam spx9_inst_0.BLK_SEL = 3'b000;
defparam spx9_inst_0.RESET_MODE = "SYNC";
defparam spx9_inst_0.INIT_RAM_00 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
defparam spx9_inst_0.INIT_RAM_01 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
defparam spx9_inst_0.INIT_RAM_02 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
defparam spx9_inst_0.INIT_RAM_03 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;

endmodule //SRAM
