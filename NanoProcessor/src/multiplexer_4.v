module multiplexer_4
  // Data size
  #(parameter N = 9)(
  input [N-1:0] in_0, [N-1:0] in_1, in_2, in_3,
  input [1:0] select,
  output reg [N-1:0] out);

  always @ (*)
    case (select)
      2'b00: out = in_0;
      2'b01: out = in_1;
      2'b10: out = in_2;
      2'b11: out = in_3;
    endcase

endmodule
