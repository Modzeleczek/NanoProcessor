module full_adder(
  input a, b, input_carry,
  output sum, output_carry);

  assign sum = input_carry ^ (a ^ b);
  assign output_carry = a & b | (a ^ b) & input_carry;

endmodule
