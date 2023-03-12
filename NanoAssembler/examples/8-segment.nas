  mvi R1 ; R1 = GPIO mode register address in processor's address space
  0b01_0000000
  ; Using R3, set 3 lowest bits of GPIO mode register to 1 in order
  ; to make the 3 lowest GPIO pins work in output mode.
  ; Set the 4th GPIO pin to input mode.
  mvi R3
  0b00000_0111
  st R3 R1 ; [R1] = R3

  mvi R0 ; R0 = constant 1 for decrementation
  1

  mvi R1 ; R1 = GPIO register address
  0b10_0000000

init_counter:
  mvi R6
  :swap_digits
  ; Load GPIO register content into R2.
  ld R2 R1 ; R2 = [R1]
  mvi R3
  0b1000
  ; Clear all GPIO bits except the 4th lowest which is the read input value.
  and R2 R3
  ; When the button is released, the 4th lowest bit of R2 is 1 because of FPGA's
  ; internal pull-up resistor.
  sub R2 R3 ; R2 -= 0b1000
  ; When the button is pressed, the 4th lowest bit of R2 is 0.
  ; Subtracting 0b1000 from 0, we get a value not equal to 0 so 'mvnz' jumps
  ; to ':swap_digits' label.
  mvnz PC R6

  mvi R6
  :first_display_position
  mvi R2
  0b100
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b101
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b000
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b001
  st R2 R6 ; [R6] = R2

  mvi PC
  :after_swap_digits

swap_digits:
  mvi R6
  :first_display_position
  mvi R2
  0b000
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b001
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b100
  st R2 R6 ; [R6] = R2

  sub R6 R0
  mvi R2
  0b101
  st R2 R6 ; [R6] = R2

after_swap_digits:
  ; Data word counter: <index (counted from 0 at the top end)
  ; of data word at the bottom end> + 2
  mvi R2 ; R2 = 35
  35

after_init_counter:
  ; Remember the address of the first instruction inside
  ; the loop over data words.
  mvi R4
  :inside_loop

  sub R2 R0 ; R2 -= 1

  mvnz PC R4 ; If R2 != 0, jump to the inside of the loop.

  mvi PC ; Otherwise, jump to resetting the loop counter.
  :init_counter

inside_loop:
  mvi R5 ; R5 = <address of the top end word> - 1
  :before_data

  ; In R5 remember the current data word index
  ; (<top end word address> + <counter>).
  add R5 R2 ; R5 += R2

  ld R3 R5 ; R3 = [R5]
  ; Note that in 'st' instruction, the destination is the second operand.
  ; It is beacuse of NanoProcessor's hardware implementation details.
  st R3 R1 ; [R1] = R3
  mvi PC ; Unconditional jump to after_init_counter
before_data:
  :after_init_counter

  ; Consecutive words written into GPIO register.
  ; We iterate over them using R2 counter starting at the bottom end.
  ; Finally, the full loop cycle writes 0001_0000_00010001 to
  ; the dual 8-bit shift register of the 8-segment display module.
  0b000 ; DIO = 0; RCLK = 0; SCLK = 0
  0b010 ; RCLK: 0 -> 1
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b101 ; tick
first_display_position:
  0b100 ; 1
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b101 ; tick
  0b100 ; 1
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b001 ; tick
  0b000 ; 0
  0b101 ; SCLK: 0 -> 1 (tick)
  0b100 ; DIO = 1
