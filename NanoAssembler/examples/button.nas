  mvi R1 ; R1 = GPIO mode register address in processor's address space
  0b01_0000000
  ; By default, all GPIO pins work in input mode because GPIO mode register has
  ; value 000000000. Nevertheless, we explicitly set the lowest GPIO pin
  ; to input mode by clearing the lowest bit of GPIO mode register.
  ; Additionally, set te second GPIO pin to output mode.
  mvi R2
  0b000000010
  st R2 R1 ; [R1] = R2

  mvi R1 ; R1 = GPIO register address
  0b10_0000000

  mvi R2 ; R2 = constant 1 for decrementation and performing 'and'
  1

  mvi R4 ; R4 = constant location of the code turning on the LED.
  :turn_on_led

loop:
  ; Load GPIO register content into R3.
  ld R3 R1 ; R3 = [R1]
  ; Clear all GPIO bits except the lowest which is the read input value.
  and R3 R2
  ; When the button is released, the lowest bit of R3 is 1 because of FPGA's
  ; internal pull-up resistor.
  sub R3 R2 ; R3 -= 1
  ; When the button is pressed, the lowest bit of R3 is 0. Subtracting 1 from 0,
  ; we get a value not equal to 0 so 'mvnz' jumps to ':turn_on_led' label.
  mvnz PC R4

  ; When the button is released, 'mvnz' does not jump so turn off the LED.
  mvi R3
  0b000000000
  st R3 R1 ; [R1] = R3

  ; Jump back to the beginning of the infinite loop.
  mvi PC
  :loop

turn_on_led:
  mvi R3
  0b000000010
  ; Set the output bit of GPIO register.
  st R3 R1 ; [R1] = R3

  ; Jump back to the beginning of the infinite loop.
  mvi PC
  :loop
