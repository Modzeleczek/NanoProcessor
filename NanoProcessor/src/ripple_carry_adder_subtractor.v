module ripple_carry_adder_subtractor
  // Added (or subtracted) number size
  #(parameter N = 4)(
  input [N-1:0] A, B,
  input sub,
  output [N-1:0] S);
  // optional carry from the last cascaded full adder
  // output cout,
  // optional overflow flag
  // output overflow);

  // carry bits for cascading full adders
  wire [N-2:0] c;
  // assign overflow = c[N-2] ^ cout;
  generate
    genvar i;
    for (i = 0; i < N; i = i + 1)
    begin: ad
      case (i)
        0: full_adder fa(A[i], sub ^ B[i], sub, S[i], c[i]);
        N-1: full_adder fa(A[i], sub ^ B[i], c[i-1], S[i],/*cout*/);
        default: full_adder fa(A[i], sub ^ B[i], c[i-1], S[i], c[i]);
      endcase
    end
  endgenerate

endmodule
