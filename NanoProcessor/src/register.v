// Parallel-in to parallel-out
module register
  // Register size
  #(parameter N = 9)(
  input [N-1:0] data,
  input load_enable, clock,
  output reg [N-1:0] value);

  initial value = {N{1'b0}};
  always @ (posedge clock)
    if (load_enable) value <= data;
    else value <= value;

endmodule
