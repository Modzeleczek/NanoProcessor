  mvi R1 ; R1 = GPIO mode register address in processor's address space
  0b01_0000000
  ; Using R3, set 2 lowest bits of GPIO mode register to 1 in order
  ; to make the 2 lowest GPIO pins work in output mode.
  mvi R3
  0b0000000_11
  st R3 R1 ; [R1] = R3

  mvi R0 ; Constant 1 for in- and decrementation
  1

  mvi R2 ; R2 = GPIO register address
  0b10_0000000

  ; Turn on the low bit LED.
  mvi R1
  0b01

start:
  st R1 R2 ; [R2] = R1

  mvi R3 ; Initialize outer loop counter.
  511

  ; In R5 store the next instruction's address
  ; which is equal to 'outer_loop_start' label's address.
  mv R5 PC

outer_loop_start:
  mvi R4 ; Initialize inner loop counter.
  511

  ; In R6 store the next instruction's address
  ; which is equal to 'inner_loop_start' label's address.
  mv R6 PC

inner_loop_start:
  sub R4 R0 ; R4 -= 1; Decrement inner loop counter.

  mvnz PC R6 ; If inner loop counter is not zero, jump to 'inner_loop_start'.

  ; Otherwise:
  sub R3 R0 ; R3 -= 1; Decrement outer loop counter.

  mvnz PC R5 ; If outer loop counter is not zero, jump to 'outer_loop_start'.

  ; Negate R1 value to swap the turned on LED.
  mvi R3 ; R3 = 0
  0
  sub R3 R1 ; R3 = -R1 = ~R1 + 1
  sub R3 R0 ; R3 = ~R1 + 1 - 1 = ~R1
  mv R1 R3 ; R1 = R3

  mvi PC ; Jump back to 'start'.
  :start
