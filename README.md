# NanoProcessor
`NanoProcessor` directory contains a single-core, multi-cycle processor implemented in Verilog hardware description language. It was tested using Tang Nano 9K development board based on Gowin GW1NR-LV9 FPGA integrated circuit. As the memory (SRAM) module, the current version of NanoProcessor uses platform-specific Gowin SPX9 IP Core documented in `documentation/UG285E.pdf` ([source](http://cdn.gowinsemi.com.cn/UG285E.pdf), accessed 17.03.2023), page 18, chapter 3.2. Therefore, to run the project on a different FPGA, the memory module should be replaced.

Tang Nano 9K FPGA development board:  
<img src="https://i.imgur.com/T8rWpDZ.jpg" width="500"/>

---
## Implementation

### Logic diagram
Below is a simplified logic diagram showing the circuit wthout going into implementation details of commonly used digital devices, e.g. a finite state machine, multiplexer, register, etc. Gray names point to Verilog files containing implementations of individual blocks.  
<img src="documentation/NanoProcessor.svg">

---
### Input/output devices
NanoProcessor uses 9-bit instruction and data words. ADDR register is used to address input/output devices and is 9 bits long. In NanoProcessor's circuit, there are 3 input/output devices available:
- static random access memory (SRAM) containing 128 9-bit words
- 9-bit GPIO mode register for selecting the working mode of corresponding GPIO register pins, i.e. 0 on i-th position sets i-th pin of GPIO register to input mode and 1 sets it to output mode
- 9-bit GPIO register

I/O devices are addressed with combination of two highest bits of ADDR register:
- 00 - SRAM; 7 lowest bits of ADDR are used to address individual words in SRAM
- 01 - GPIO mode register; 7 lowest bits of ADDR are unused
- 10 - GPIO register; 7 lowest bits of ADDR are unused
- 11 - unused

---
### General-purpose registers
NanoProcessor has 8 general-purpose registers having 3-bit codes and being accessible by the programmer. The first 7 are parallel-in to parallel-out registers. The last is the program counter which can be operand of instructions (described in the next paragraph) just like the 7 'normal' registers.

General-purpose registers:
mnemonic name | code (decimal) | code (binary)
--------------|----------------|--------------
R0            | 0              | 000
R1            | 1              | 001
R2            | 2              | 010
R3            | 3              | 011
R4            | 4              | 100
R5            | 5              | 101
R6            | 6              | 110
R7 (PC)       | 7              | 111

---
### Instructions
IR is instruction register storing instruction words interpreted by the control unit. The processor can perform 8 instructions, each of which has 3 bits long code.

The control unit is a finite state machine synchronized with processor's input clock signal. By default, in every clock tick (also known as clock cycle) all control unit's output signals have value 0. To implement an instruction, we set some of the outputs to value 1. This causes various blocks of the processor to pass, block or transform data which eventually gets to the place desired by the designer.

The table below shows how exactly each NanoProcessor's instruction is implemented. Column T0 lists all control unit's output signals having value 1 during 0th clock tick of the currently performed instruction. Column T1 lists signals during 1st clock tick, etc. An exception from the rule is `alu_op` signal which is 2 bits long so its values are listed as 2-bit combinations.

`Done` signal set by the control unit is a sign that execution of the current instruction will be finished on the next clock edge. `_out` signals tell the bus multiplexer to pass the word from the specified input to its output. Similarly, `_in` signals tell various blocks of the processor to load on the next clock edge the word passed by the bus multiplexer. `incr_PC` tells the program counter to increment by one on the next clock edge. `Write_D` is the input value of `Write` register which tells the input/output device selected by ADDR to read the word from DOUT. `zero_G` indicates if the value of G register is equal to 0.

All instructions begin with the same ticks T0, T1, T2. It is because regardless of which instruction will be performed, the processor must firstly load it. The following operations are done during the first 3 ticks:
- On the clock edge between T0 and T1 the value of program counter (R7 a.k.a. PC) is loaded into ADDR register.
- Gowin SPX9 SRAM implementation has one clock cycle delay while reading data. Therefore, during T1 the processor waits for SRAM. On the clock edge between T1 and T2 SRAM sends the read word to its outputs and the program counter is incremented.
- On the clock edge between T2 and T3 the word from SRAM is loaded into instruction register (IR) and starting from T3, it is interpreted as instruction word by the control unit which executes the instruction.

Some operations reading SRAM must have delay ticks like T1 mentioned above. Examples of such delay ticks are T4 of `mvi` and T4 of `ld`. Execution of different operations can take varying number of ticks, e.g. `mv` takes only 4 ticks, while `add` takes 6 ticks.

Implementation of all instructions currently supported by NanoProcessor:
mnemonic name | code (decimal) | code (binary) | T0 | T1 | T2 | T3 | T4 | T5
--------------|----------------|---------------|----|----|----|----|----|---
mv   | 0 | 000 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[y], R_in[x], Done             |                                  |
mvi  | 1 | 001 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[7], ADDR_in, incr_PC          | (waiting for SRAM)               | DIN_out, R_in[x], Done
add  | 2 | 010 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[x], A_in                      | R_out[y], G_in, alu_op = 00      | G_out, R_in[x], Done
sub  | 3 | 011 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[x], A_in                      | R_out[y], G_in, alu_op = 01      | G_out, R_in[x], Done
ld   | 4 | 100 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[y], ADDR_in                   | (waiting for SRAM)               | DIN_out, R_in[x], Done
st   | 5 | 101 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[y], ADDR_in                   | R_out[x], DOUT_in, Write_D, Done |
mvnz | 6 | 110 | R_out[7], ADDR_in | incr_PC | IR_in | Done, if ~zero_G: R_out[y], R_in[x] |                                  |
and  | 7 | 111 | R_out[7], ADDR_in | incr_PC | IR_in | R_out[x], A_in                      | R_out[y], G_in, alu_op = 10      | G_out, R_in[x], Done
<!-- aligned headers for Markdown code readability
name  dec  bin   T0                  T1        T2      T3                                    T4                         T5 -->

The listed instructions can be divided into 2 groups:
1. Register instructions

    A register instruction has 2 operands being register codes.

    - mv Rx Ry

        Copies Ry to Rx.

    - add Rx Ry

        Adds Ry to Rx and stores the result in Rx.

    - sub Rx Ry

        Subtracts Ry from Rx and stores the result in Rx.

    - ld Rx Ry

        Stores in Rx the value read from I/O device addressed by Ry.

    - st Rx Ry

        Writes the value of Rx to I/O device addressed by Ry. Note that the address must be in Ry, not Rx.

    - mvnz Rx Ry

        An arithmetic or logic instruction (`add`, `sub` or `and`) must immediately precede `mvnz`. Supposing that this condition is satisfied, `mvnz Rx Ry` works just like `mv Rx Ry` if the result of the previous instruction was not equal to 0 or it does nothing if the result was equal to 0. If the requirement is not met, `mvnz` behavior is undefined.

    - and Rx Ry

        Performs bitwise AND on Rx and Ry and stores the result in Rx.

2. Immediate instructions

    An immediate instruction is followed by 2 register codes as well. The first operand is a standard register code. Unlike register instruction, in this case the second register code is ignored by the control unit so it can be any 3-bit number. The real second operand of an immediate instruction is the word immediately following it.
    - mvi Rx  
    data (an arbitrary 9-bit number)

        Copies `data` value to Rx register.

---
## Running

### Requirements
First of all, you need an FPGA to run NanoProcessor. The most reliable method is to use Tang Nano 9K FPGA development board because it has already been tested and seems to work. Unfortunately, NanoProcessor uses Gowin SPX9 IP Core as SRAM module so the project without any modifications can only be run using proprietary Gowin EDA, also known as Gowin FPGA Designer.

---
### Steps for Windows operating system
1. Download and install Gowin EDA from [the producer's page](https://www.gowinsemi.com/en/support/download_eda/). NanoProcessor was tested on Gowin EDA 1.9.8.03 Education (build 56847).

2. To open the project, open file `NanoProcessor.gprj` in Gowin EDA.

3. In file `src/pins.cst` assign physical FPGA pin numbers to ports of NanoProcessor top-level module: input `clock` and input/output `gpio`.

    According to `documentation/Tang_Nano_9K_3672_Schematic.pdf` ([source](https://dl.sipeed.com/shareURL/TANG/Nano%209K/2_Schematic), accessed 17.03.2023), page 2, Tang Nano 9K on-board crystal oscillator generating 27 MHz squarewave is connected to pin 52 of GW1NR-LV9 FPGA.

    Tang Nano 9K goldpin numbers are shown on the board so they can be easily used to assign `gpio` in `pins.cst`.  
    <img src="https://i.imgur.com/mkMKGcY.jpg" width="500"/>

4. Write the program to be performed by NanoProcessor starting from line 45 (`defparam spx9_inst_0.INIT_RAM_00`) of file `src/SRAM.v`. Obviously, manually writing a program in binary code is slow, so you can use NanoAssembler.

5. Save `pins.cst` and `SRAM.v` and run `Synthesize` and `Place & Route` operations.

6. Connect Tang Nano 9K to your computer via USB.

7. Open `Tools > Programmer` and make sure the only record is

    .| Enable | Series   | Device   | Operation    | FS File
    -|--------|----------|----------|--------------|---------
    1| ✓      | GW1NR    | GW1NR-9C | SRAM Program | path to `NanoProcessor/impl/pnr/NanoProcessor.fs`

    Operation can differ from `SRAM Program` when you want to write the FPGA configuration to embedded or external flash memory. Nevertheless, running from flash has not been tested yet.

8. Click `Edit > Program/Configure` to write the configuration to the FPGA.


# NanoAssembler
NanoAssembler is a Python script translating a text file written in NanoAssembly language to NanoProcessor machine (binary) code.

---
## Syntax

### Tokens
A program in NanoAssembly is parsed from top to bottom and from left to right. It consists of several components called tokens in terms of syntax analysis (parsing) performed by NanoAssembler script. 2 consecutive tokens in a program are separated with any number of whitespace characters. Below is the list of recognized tokens:

1. Literal

    It is a decimal number (e.g. `5`) or a binary number with prefix `0b` (e.g. `0b101`).

2. Newline

    It is an end of line sequence. NanoAssembler recognizes 3 popular newline sequences: LF (`\n`), CR (`\r`), CRLF (`\r\n`).

3. Comment

    Starts with `;` character and causes the parser to ignore all characters until it meets a newline token. Currently, only single-line comments are supported.

4. Register instruction mnemonic name

    It is a name from the list: `mv, add, sub, ld, st, mvnz, and`. This token is case-sensitive so it must be written in lowercase.

5. Immediate instruction mnemonic name

    It can only be name `mvi`. Again, this token must be written in lowercase.

6. Register mnemonic name

    It is a name from the list: `R0, R1, R2, R3, R4, R5, R6, PC`. This time, it must be written in uppercase.

7. Label declaration

    It is an arbitrary word followed by `:` character (e.g. `some_label:`). NanoAssembler calculates the address of the first literal or instruction following the label declaration. The calculated address is substituted for all references to that label. Label redeclarations cause NanoAssembler to print warnings.

8. Label reference

    It is an arbitrary word preceded by `:` character (e.g. `:some_label`). A label can be referenced in the entire program, even before its declaration. A reference to undeclared label produces an error and stops NanoAssembler.

Unrecognized tokens, which are of none of the types listed above, cause NanoAssebler to print an error and stop.

---
### Instructions
A single instruction definition consists of multiple properly ordered tokens.  
A register instruction is defined by writing:
- mnemonic name of the instruction,
- mnemonic name of the first register operand,
- mnemonic name of the second register operand,
- exactly 1 newline.

Similarly, an immediate instruction is defined by writing:
- mnemonic name of the instruction,
- mnemonic name of the first register operand,
- exactly 1 newline,
- (optional) 1 or more label declarations and/or newlines,
- exactly 1 literal or label reference.
- exactly 1 newline.

No tokens other than comments can be located between the listed tokens. Otherwise, NanoAssembler produces an unexpected token error and stops.

---
## Usage

### Running
To run NanoAssembler, only Python (at least 3.11.0) is required. The script has optional source file encoding detection feature. To use it, `chardet` Python module must be available. Below is the script's usage description:
```
usage: NanoAssembler [-h] [-e SOURCE_ENCODING] [-o TARGET] source

Translate a file written in NanoAssembly language to NanoProcessor machine (binary) code.

positional arguments:
  source              Path to a text file written in NanoAssembly language.

options:
  -h                  Show this help message and exit.
  -e SOURCE_ENCODING  Specify encoding of the source file. See 'codecs' Python module for the list of supported encodings
                      (https://docs.python.org/3/library/codecs.html#standard-encodings). If source encoding is not specified, NanoAssembler attempts to
                      determine it using 'chardet' Python module as long as the user has it installed. Do not use automatic encoding detection for big files
                      that cannot entirely fit in Python script's memory. Such a program probably would not fit in NanoProcessor's memory anyway.
  -o TARGET           Overwrite initial memory content in specified SRAM module Verilog file (SRAM.v). If this argument is not used, the machine code is
                      written to stdout.
```

---
### Basic examples
The examples below assume that file `program.nas` contains the following code:
```
mvi R0 R1 ; comment
label0: label1:
5

:label0
:label1
```

1. Assembling to stdout with source encoding detection

    Command:
    ```
    python NanoAssembler.py program.nas
    ```

    Output:
    ```
    Detected source encoding 'ascii'.
    001000000
    000000101
    000000001
    000000001
    ```

2. Assembling to SRAM.v file

    Command:
    ```
    python NanoAssembler.py program.nas -e utf_8 -o ../NanoProcessor/src/SRAM.v
    ```

    The script does not print anything to stdout but its output is written to SRAM.v file:
    ```
    defparam spx9_inst_0.INIT_RAM_00 = 288'h000000000000000000000000000000000000000000000000000000000000000008040A40;
    defparam spx9_inst_0.INIT_RAM_01 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
    defparam spx9_inst_0.INIT_RAM_02 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
    defparam spx9_inst_0.INIT_RAM_03 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
    ```
    After that, Gowin EDA can be used to write the new NanoProcessor configuration to the FPGA (see `NanoProcessor > Running > Steps for Windows operating system > step 4`).

---
### Complex examples
NanoAssembly code for examples shown below is located in `examples` directory.
#### 1. 2 leds
To build this example, use `NanoAssembler`
```
python NanoAssembler.py examples/2_leds.nas -e utf_8 -o ../NanoProcessor/src/SRAM.v
```

This example presents an infinite loop with delay and how to use NanoProcessor's GPIO in output mode.  
[<img src="https://i.imgur.com/615szSH.png" width="500"/>](https://youtu.be/9xZs03qSoGM)  
(Click the image to watch the presentation on YouTube.)

GPIO signals can be seen with such a logic analyzer:  
<img src="https://i.imgur.com/J6dOCDb.jpg" width="500"/>

One period of the squarewaves driving LEDs takes 194.2 milliseconds.  
<img src="https://i.imgur.com/kOJrR7P.png"/>

#### 2. Button
In this example, a button acts as SPST (Single Pole Single Throw) switch. When the button is pressed, it shorts GPIO pin 0 (FPGA pin 38) to ground and GPIO register's 0th bit is cleared (has value 0). Due to GW1NR-LV9 FPGA's default pull-up resistor mode, when the button is released, GPIO pin 0 is charged up to high logic level electric potential and GPIO register's 0th bit is set (has value 1).  
[<img src="https://i.imgur.com/KgtvpSn.png" width="500"/>](https://youtu.be/g65piavEohw)

When the button is 0 (pressed), the LED is 1.
<img src="https://i.imgur.com/CUkzJ9o.png"/>

#### 3. 8-segment display
This example presents how NanoProcessor displays a single character on a 4-digit 8-segment LED display module based on two 75HC595 shift registers connected in series. For details on the module, see `Display` example in [my PineA64GPIO repository](https://github.com/Modzeleczek/PineA64GPIO#2-display).

[<img src="https://i.imgur.com/l9ViVYF.png" width="500"/>](https://youtu.be/vWWecErREPk)

DIO carries the data word written into the shift register. SCLK is the clock signal (with period equal to 3 microseconds) that causes the shift register to change its state. RCLK is ticked once every a complete data word to make the shift register's latch pass the word to its output pins.
<img src="https://i.imgur.com/tF3hCoz.png"/>
