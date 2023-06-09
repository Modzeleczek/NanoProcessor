module NanoProcessor(
  input clock,
  inout [8:0] gpio);

  /* To slow down 'clock' by frequency division, uncomment the below
  timer instantiation, change the name of 'input clock' in module header
  to 'input fast_clock' and change the name of 'clock' to 'fast_clock' in pins.cst.
  Timer module parameter determines how many 'fast_flock' cycles must occur in order
  to flip the value of 'clock'. Therefore, set 'TIMEOUT' to N if you want 'clock' to
  be 'fast_clock' divided by 2*N, e.g. if 'fast_clock' is 27 MHz square wave and
  'TIMEOUT' is 13_500_000, then 'clock' is 1 Hz square wave. */
  // timer #(13_500) t(fast_clock, clock);

  wire [8:0] DIN, ADDR, DOUT;
  wire Write;
  processor proc(DIN, 1'b1, clock, 1'b1, ADDR, DOUT, Write);

  wire ignore, sram_wr_en, mode_wr_en, gpio_wr_en;
  decoder_2_to_4 IO_write_selector(ADDR[8:7], Write,
    {ignore, gpio_wr_en, mode_wr_en, sram_wr_en});

  // General-purpose input/output
  wire [8:0] mode_out;
  // Register for setting input or output mode of GPIO pins.
  register #(9) reg_mode(DOUT, mode_wr_en, clock, mode_out);
  GPIO_register #(9) reg_GPIO(clock, mode_out, DOUT, gpio_wr_en, gpio);

  wire [8:0] sram_out;
  /* Two highest bits of ADDR select which input/output device
  passes its output to processor bus input: SRAM,
  GPIO mode register or GPIO register. */
  multiplexer_4 DIN_multiplexer(sram_out, mode_out, gpio, 9'd0,
    ADDR[8:7], DIN);

  // SPX9 (Single Port 18K BSRAM); UG285E.pdf, page 18, chapter 3.2
  SRAM sram(
    .dout(sram_out), // Data output
    .clk(clock), // Synchronizing clock
    .oce(1'b1), // Output clock enable unused in bypass read mode
    .ce(1'b1), // Clock enable, active-high
    .reset(1'b0), // Reset, active-high
    .wre(sram_wr_en), // Write enable: 1 - write, 0 - read
    .ad(ADDR[6:0]), // Address input
    .din(DOUT) // Data input
  );

endmodule
