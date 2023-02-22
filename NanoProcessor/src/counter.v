module counter
  // Size of the counter value number in bits
  #(parameter N = 4)(
  /* Asynchronous resetting and loading synchronized
  with 'clock' */
  input areset, count_enable, sload, clock,
  input [N-1:0] data,
  output reg [N-1:0] value);

  initial value = {N{1'b0}};
  always @ (posedge clock, negedge areset)
    if (~areset) value = {N{1'b0}};
    else if (sload) value <= data;
    else if (count_enable) value <= value + 1'b1;
    else value <= value;

endmodule
