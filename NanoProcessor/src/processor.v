module processor(
  input [8:0] DIN, // Data passed to the processor by an input/output device

  /* Asynchronous active-low reset, i.e. if 0, the processor resets
  instantaneously and then resets on every 'Clock' positive edge. */
  input Resetn,
  
  /* A signal that has sufficienly steep positive edges to trigger the FPGA's
  internal D flip-flops. */
  Clock,

  /* 1 allows to start the execution of a 9-bit word currently pointed to by
  'ADDR'. 0 prevents execution. */
  Run,

  /* Used to point to an i/o device available in processor's address space.
  I/o device can be a SRAM module, a register (e.g. GPIO register), etc. */
  output [8:0] ADDR,
  
  DOUT, // Data to be written to the address in 'ADDR'

  /* Register Write output signal used to inform the i/o device addressed
  in 'ADDR' that it should read data from 'DOUT'.
  (if 0, the i/o device should write data to processor's 'DIN' input). */
  output Write);

  /* The processor's control unit is a finite state machine (FSM).
  Below are FSM state codes. During execution of an instruction,
  every 'Clock' positive edge makes FSM go to the next state,
  i.e. T0 -> T1 -> T2 -> T3 -> T4 -> T5 -> T0. Some instructions
  take less than 6 clock cycles, e.g. for an instruction taking 4 cycles,
  the transitions are: T0 -> T1 -> T2 -> T3 -> T0. */
  localparam [2:0] T0 = 3'b000, T1 = 3'b001, T2 = 3'b010, T3 = 3'b011,
    T4 = 3'b100, T5 = 3'b101;
  // Instruction binary codes
  localparam [2:0] mv = 3'b000, mvi = 3'b001, add = 3'b010, sub = 3'b011,
    ld = 3'b100, st = 3'b101, mvnz = 3'b110, and_ = 3'b111;

  reg [8:0] Bus; // Output signal of the 9-bit bus multiplexer
  /* One-hot (1-of-8) signals indicating registers
  affected by currently executed instruction */
  wire [0:7] Xreg, Yreg;

  // Instruction code part of instruction register (IR) output signal
  wire [2:0] I;

  // Output signal of instruction register
  wire [9:1] IR;

  // Output signal of buffer register storing the first ALU operand
  wire [8:0] A,
  // Output signal of buffer register storing the result of an ALU operation
  G;

  /* R0 - R6 are output signals of 9-bit general-purpose registers
  accessible by the programmer. PC is output signal of a 9-bit
  program counter that can be accessed like it was R7 register. */
  wire [8:0] R0, R1, R2, R3, R4, R5, R6, PC;
  /* Indicates if the last arithmetic logic unit's operation
  resulted in 0 value. */
  wire zero_G = (G == 9'b000000000);

  /* FSM output signals
  FSM uses '*_in' signals to enable writing on the next positive edge of 'Clock'
  signal to the register named *.
  Similarly, FSM uses '*_out' signals to force the bus multiplexer to pass
  the value of the register named * to the bus. */

  reg IR_in; // Register IR enable for writing

  /* 1 on corresponding position forces the bus multiplexer
  to put the value of register R0 - R7 (PC) on the bus. */
  reg [0:7] R_out;

  // 1 forces the bus multiplexer to put the value of register G on the bus.
  reg G_out,
  // 1 forces the bus multiplexer to put the value of DIN on the bus.
  DIN_out,
  // 1 enables PC to increment its value on the next positive edge of 'Clock'.
  incr_PC;

  reg [0:7] R_in; // Register R0 - R7 (PC) enable signal for writing

  reg A_in, // Register A enable for writing
  G_in, // Register G enable for writing
  ADDR_in, // Register ADDR enable for writing
  DOUT_in, // Register DOUT enable for writing
  Write_D, // Register Write input signal
  /* Used by FSM to inform anybody interested that the processor will
  finish executing the current instruction on the next 'Clock' positive edge. */
  Done;

  reg [1:0] alu_op; // Arithmetic logic unit operation code

  wire [8:0] alu_res; // Output signal of the arithmetic logic unit

  /* Below are output and input of an implicit register
  (consisting of 3 D flip-flops) storing the current FSM state code. */
  reg [2:0] Tstep_Q; // Current FSM state code
  reg [2:0] Tstep_D; // Next FSM state code

  assign I = IR[9:7];
  decoder_3_to_8 decX(IR[6:4], 1'b1, Xreg);
  decoder_3_to_8 decY(IR[3:1], 1'b1, Yreg);

  // Determine the next FSM state.
  always @ (Tstep_Q, Run, Done)
    case (Tstep_Q)
      T0:
        /* Run must be 1 to start execution of the instruction
        whose address is currently pointed to by PC (R7).
        Tstep_D stores the code of the next state of FSM. */
        if (~Run) Tstep_D = T0;
        else Tstep_D = T1;
      T1:
        if (Done) Tstep_D = T0;
        else Tstep_D = T2;
      T2:
        if (Done) Tstep_D = T0;
        else Tstep_D = T3;
      T3:
        if (Done) Tstep_D = T0;
        else Tstep_D = T4;
      T4:
        if (Done) Tstep_D = T0;
        else Tstep_D = T5;
      default: // only T5
        Tstep_D = T0;
    endcase
  
  // Determine FSM output signals in all possible FSM states: T0 - T5.
  always @ (Tstep_Q, I, Xreg, Yreg, zero_G) begin
    /* In every state, firstly assume that all signals are 0 and then
    set required ones to 1 in accordance with currently executed instruction
    whose code is stored in IR.
    Assignment of multiple signals in one line. It is equivalent to
    writing 'Done = 1'b0; G_in = 1'b0...' and 'R_in = 8'b0000_0000;
    R_out = 8'b0000_0000;'
    {Done, G_in, G_out, A_in, alu_op, DIN_out, IR_in, incr_PC,
      ADDR_in, DOUT_in, Write_D} = 12'b000000000000;
    {R_in, R_out} = 16'b00000000_00000000; */
    Done = 1'b0;
    G_in = 1'b0;
    G_out = 1'b0;
    A_in = 1'b0;
    alu_op = 2'b00;
    DIN_out = 1'b0;
    R_in = 8'b0000_0000;
    R_out = 8'b0000_0000;
    IR_in = 1'b0;
    incr_PC = 1'b0;
    ADDR_in = 1'b0;
    DOUT_in = 1'b0;
    Write_D = 1'b0;
    case (Tstep_Q)
      T0: begin // FSM output signals in state T0
        R_out[7] = 1'b1;
        ADDR_in = 1'b1;
      end
      T1: begin // FSM output signals in state T1
        /* At the next clock edge SRAM module will put the read
        word (instruction or data) to DIN input of the processor */
        incr_PC = 1'b1;
      end
      T2: begin // FSM output signals in state T2
        IR_in = 1'b1;
      end
      T3: // FSM output signals in state T3
        case (I)
          mv: begin
            R_out = Yreg;
            R_in = Xreg;
            Done = 1'b1;
          end
          mvi: begin
            R_out[7] = 1'b1;
            ADDR_in = 1'b1;
            incr_PC = 1'b1;
          end
          add, sub, and_: begin
            R_out = Xreg;
            A_in = 1'b1;
          end
          ld, st: begin
            R_out = Yreg;
            ADDR_in = 1'b1;
          end
          mvnz: begin
            Done = 1'b1;
            if (~zero_G) begin
              R_out = Yreg;
              R_in = Xreg;
            end
          end
        endcase
      T4: // FSM output signals in state T4
        case (I)
          /* mvi: I/o device puts read data to DIN
          input of the processor. */
          add: begin
            R_out = Yreg;
            G_in = 1'b1;
            alu_op = 2'b00;
          end
          sub: begin
            R_out = Yreg;
            G_in = 1'b1;
            alu_op = 2'b01;
          end
          /* ld: In state T4 the processor is waiting
          for i/o device to put read data to DIN. */
          st: begin
            R_out = Xreg;
            DOUT_in = 1'b1;
            Write_D = 1'b1;
            Done = 1'b1;
          end
          and_: begin
            R_out = Yreg;
            G_in = 1'b1;
            alu_op = 2'b10;
          end
        endcase
      T5: // FSM output signals in state T5
        case (I)
          mvi: begin // Data from i/o device is already on DIN.
            DIN_out = 1'b1;
            R_in = Xreg;
            Done = 1'b1;
          end
          add, sub, and_: begin
            G_out = 1'b1;
            R_in = Xreg;
            Done = 1'b1;
          end
          ld: begin // Data from i/o device is already on DIN
            DIN_out = 1'b1;
            R_in = Xreg;
            Done = 1'b1;
          end
        endcase
    endcase
  end

  /* Perform FSM state transitions by inserting
  the new state code into FSM state flip-flops. */
  always @ (posedge Clock, negedge Resetn)
    if (~Resetn) Tstep_Q <= T0;
    else Tstep_Q <= Tstep_D;

  // Registers
  register #(9) reg_0(Bus, R_in[0], Clock, R0);
  register #(9) reg_1(Bus, R_in[1], Clock, R1);
  register #(9) reg_2(Bus, R_in[2], Clock, R2);
  register #(9) reg_3(Bus, R_in[3], Clock, R3);
  register #(9) reg_4(Bus, R_in[4], Clock, R4);
  register #(9) reg_5(Bus, R_in[5], Clock, R5);
  register #(9) reg_6(Bus, R_in[6], Clock, R6);
  counter #(9) cnt_pc(Bus, Resetn, incr_PC, R_in[7], Clock, PC);
  register #(9) reg_A(Bus, A_in, Clock, A);
  register #(9) reg_G(alu_res, G_in, Clock, G);
  register #(9) reg_IR(DIN, IR_in, Clock, IR);
  register #(9) reg_ADDR(Bus, ADDR_in, Clock, ADDR);
  register #(9) reg_DOUT(Bus, DOUT_in, Clock, DOUT);
  register #(1) reg_Write(Write_D, 1'b1, Clock, Write);

  // Arithmetic logic unit
  arithmetic_logic_unit #(9) alu(A, Bus, alu_op, alu_res);

  // Main 9-bit bus multiplexer
  wire [0:9] mux_s;
  assign mux_s = {DIN_out, R_out, G_out};
  always @ (*)
    case (mux_s)
      default: Bus = DIN; // 10'b1000000000
      10'b0100000000: Bus = R0;
      10'b0010000000: Bus = R1;
      10'b0001000000: Bus = R2;
      10'b0000100000: Bus = R3;
      10'b0000010000: Bus = R4;
      10'b0000001000: Bus = R5;
      10'b0000000100: Bus = R6;
      10'b0000000010: Bus = PC;
      10'b0000000001: Bus = G;
    endcase

endmodule
