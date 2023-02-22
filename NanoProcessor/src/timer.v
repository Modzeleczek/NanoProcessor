module timer
  /* Number of clock cycles after which 'toggled' changes
  value to its negative. Simply, 'toggled' is 'clock' signal
  divided by 2*TIMEOUT. */
  #(parameter TIMEOUT = 13_500_000)
  (input clock,
  output reg toggled);

  // Returns size in bits of 'v'.
  function integer size_of(input [31:0] v);
    for (size_of = 0; v > 0; size_of = size_of + 1)
      v = v >> 1;
  endfunction

  localparam N = size_of(TIMEOUT - 1);

  initial toggled = 1'b0;
  reg [N-1:0] counter = TIMEOUT - 1;
  always @ (posedge clock)
    if (counter == 0) begin
      counter <= TIMEOUT - 1;
      toggled <= ~toggled;
    end
    else counter <= counter - 1;

endmodule
