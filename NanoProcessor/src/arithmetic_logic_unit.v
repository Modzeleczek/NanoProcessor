module arithmetic_logic_unit
  // Operands' size
  #(parameter N = 4)(
  input [N-1:0] A, B,
  /* Operation codes: 01 - sub, 10 - and, other - add */
  input [1:0] operation_code,
  output [N-1:0] result);

  wire [N-1:0] add_sub_out;
  ripple_carry_adder_subtractor #(N) add_sub(
    A, B, operation_code[0], add_sub_out);

  reg [N-1:0] r;
  assign result = r;
  always @ (*)
    case (operation_code)
      2'b00: r = add_sub_out; // Add
      2'b01: r = add_sub_out; // Subtract
      2'b10: r = A & B; // And
      2'b11: r = add_sub_out; // Subtract
    endcase

endmodule
