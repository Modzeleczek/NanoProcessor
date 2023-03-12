/* A bidirectional register with mode selection bits
is implemented using tri-state buffers.

'From_processor' signal should be connected to the data output of
the processor's bus.
'To_processor' signal should be connected to the data input of
the processor's bus.
'Pin' signal should be connected to physical input/output pins.

When mode[i] == 0, the tri-state buffer pin[i] has high impedance.
Some external device should pull pin[i] high (1) or low (0) to set its value.
The processor can read pin[i] value using to_processor[i] signal.

When mode[i] == 1, the tri-state buffer pin[i]
has value equal to signal from_processor[i]. */
module GPIO_register
  // Register size
  #(parameter N = 9)(
  input clock,
  input [N-1:0] mode,
  input [N-1:0] from_processor,
  input load_enable,
  // output [N-1:0] to_processor,
  inout [N-1:0] pin);

  reg [8:0] value = {N{1'b0}};
  assign pin = value;

  generate
    genvar i;
    for (i = 0; i < N; i = i + 1)
    begin: gen
      always @ (posedge clock)
        if (~mode[i]) value[i] <= 1'bZ;
        else if (load_enable) value[i] <= from_processor[i];
        else value[i] <= value[i];
    end
  endgenerate

endmodule
