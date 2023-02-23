module NanoProcessor(
  input clock,
  output [8:0] gpio);

  /* To slow down 'clock' by frequency division, uncomment the below
  timer instantiation, change the name of 'input clock' in module header
  to 'input fast_clock' and change the name of 'clock' to 'fast_clock' in pins.cst.
  Timer module parameter determines how many 'fast_flock' cycles must occur in order
  to flip the value of 'clock'. Therefore, set 'TIMEOUT' to N if you want 'clock' to
  be 'fast_clock' divided by 2*N, e.g. if 'fast_clock' is 27 MHz square wave and
  'TIMEOUT' is 13_500_000, then 'clock' is 1 Hz square wave. */
  // timer #(13_500) t(fast_clock, clock);

  wire [8:0] DIN, ADDR, DOUT;
  wire W;
  processor proc(DIN, 1'b1, clock, 1'b1, ADDR, DOUT, W);

  wire wr_en = (~(ADDR[7] | ADDR[8])) & W;
  // Only general-purpose output
  wire enable_gpio = (~((~ADDR[7]) | ADDR[8])) & W;
  register #(9) reg_GPIO(DOUT, enable_gpio, clock, gpio);

  // SPX9 (Single Port 18K BSRAM); UG285E.pdf, page 18, chapter 3.2
  SRAM sram(
    .dout(DIN), // Data output
    .clk(clock), // Synchronizing clock
    .oce(1'b1), // Output clock enable unused in bypass read mode
    .ce(1'b1), // Clock enable, active-high
    .reset(1'b0), // Reset, active-high
    .wre(wr_en), // Write enable: 1 - write, 0 - read
    .ad(ADDR[6:0]), // Address input
    .din(DOUT) // Data input
  );

endmodule
