  mvi R0 ; R0 = 1
  1

  mvi R1 ; R1 = GPIO register address in processor's address space
  0b01_0000000

init_counter:
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
