module decoder_2_to_4(
  input [1:0] binary,
  input enable,
  output reg [3:0] one_hot);

  always @ (*)
    if (enable)
      case (binary)
        2'b00: one_hot = 4'b0001;
        2'b01: one_hot = 4'b0010;
        2'b10: one_hot = 4'b0100;
        2'b11: one_hot = 4'b1000;
      endcase
    else
      one_hot = 4'b0000;

endmodule
