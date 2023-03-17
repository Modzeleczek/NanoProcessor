from __future__ import annotations
import argparse
from io import TextIOWrapper
import os
import sys
from typing import TextIO
import codecs
from types import SimpleNamespace
from collections import deque

# Token types
class Token(object):
  def __init__(self, raw: str, line: int, column: int) -> None:
    self.raw = raw # Public attribute
    # Index of the line and text column in which the token was met.
    self.line = line
    self.column = column

  def description(self) -> str: # Consider this public abstract method.
    raise NotImplementedError("Please implement this method")

class Newline(Token):
  def __init__(self, token: Token) -> None:
    super().__init__(token.raw, token.line, token.column)

  def try_parse(token: Token) -> Newline:
    if token.raw == "\n":
      return Newline(token)
    return None

  def description(self) -> str:
    return "newline"

class LabelDeclaration(Token):
  def __init__(self, token: Token) -> None:
    super().__init__(token.raw, token.line, token.column)

  def try_parse(token: Token) -> LabelDeclaration:
    if token.raw.endswith(":"):
      return LabelDeclaration(token) # Do not skip ":".
    return None

  def name(self) -> str:
    return self.raw[:-1] # Skip ":".

  def description(self) -> str:
    return f"label declaration '{self.raw}'"

class Instruction(Token):
  def __init__(self, token: Token) -> None:
    super().__init__(token.raw, token.line, token.column)

  def bit_count(self) -> int:
    return 3

  def numeric_value(self) -> int:
    return self.CODES[self.raw]

class RegisterInstruction(Instruction):
  CODES = { "mv":0, "add":2, "sub":3, "ld":4, "st":5, "mvnz":6, "and":7 }

  def __init__(self, token: Token) -> None:
    super().__init__(token)

  def try_parse(token: Token) -> RegisterInstruction:
    codes = RegisterInstruction.CODES
    if token.raw in codes:
      return RegisterInstruction(token)
    return None

  def description(self) -> str:
    return f"register instruction '{self.raw}'"

class ImmediateInstruction(Instruction):
  # 'mvi' is 'immediate' instruction whose second operand must
  # be specified immediately after the instruction word.
  CODES = { "mvi":1 }

  def __init__(self, token: Token) -> None:
    super().__init__(token)

  def try_parse(token: Token) -> ImmediateInstruction:
    codes = ImmediateInstruction.CODES
    if token.raw in codes:
      return ImmediateInstruction(token)
    return None

  def description(self) -> str:
    return f"immediate instruction '{self.raw}'"

class Register(Instruction):
  CODES = { "R0":0, "R1":1, "R2":2, "R3":3, "R4":4, "R5":5, "R6":6, "PC":7 }

  def __init__(self, token: Token) -> None:
    super().__init__(token)

  def try_parse(token: Token) -> Register:
    codes = Register.CODES
    if token.raw in codes:
      return Register(token)
    return None

  def description(self) -> str:
    return f"register name '{self.raw}'"

class NumericValue(Token):
  def __init__(self, token: Token) -> None:
    super().__init__(token.raw, token.line, token.column)

  def bit_count(self) -> int:
    return 9

class LabelReference(NumericValue):
  def __init__(self, token: Token) -> None:
    super().__init__(token)

  def try_parse(token: Token) -> LabelReference:
    if token.raw.startswith(":"):
      return LabelReference(token) # Do not skip ":".
    return None

  def name(self) -> str:
    return self.raw[1:] # Skip ":".

  def description(self) -> str:
    return f"label reference '{self.raw}'"

  def bit_count(self) -> int:
    return 9

class Literal(NumericValue):
  def __init__(self, token: Token) -> None:
    super().__init__(token)

  def try_parse(token: Token) -> Literal:
    if Literal.__value(token.raw) is not None:
      return Literal(token)
    return None

  def __value(raw: str) -> int:
    if raw.startswith("0b"): # Binary number literal
      # Full slice syntax is start(inclusive):stop(exclusive):step
      # -1 is the index of the last element, -2 is before the last, etc.
      # If start is omitted, all elements to the left from stop are taken.
      # If stop is omitted, all elements to the right from start are taken.
      digits = raw[2:] # Skip "0b".
      base = 2
    else: # Decimal number literal
      digits = raw
      base = 10

    length = len(digits)
    if not (length > 0): # Number has no digits.
      return None

    return Literal.str_to_int(digits, base)

  def str_to_int(digits: str, base: int) -> int:
    # Assume that base <= 16
    # Assume that standard ASCII characters have the same code point
    # (result of 'ord' function) in all possible source encodings.
    # e.g. "0" has code point 48, "9" has 57, "a" has 97, etc.
    digit_values = dict[str]()
    ord_counter = ord("0")
    code = 0
    for i in range(0, min(base, 10)): # Populate up to 9 or less if base < 10.
      digit_values[chr(ord_counter)] = code
      ord_counter += 1
      code += 1
    ord_counter = ord("a")
    for i in range(10, base): # Does not run if base <= 10.
      digit_values[chr(ord_counter)] = code
      ord_counter += 1
      code += 1

    length = len(digits)
    number = 0
    power = 1 # base^0
    for i in range(length - 1, -1, -1): # Loop from length - 1 to 0.
      char = digits[i]
      if char == "_": # Skip "_".
        pass
      elif char in digit_values:
        number += digit_values[char] * power
        if number >= 512: # The processor uses 9-bit data and instruction words.
          return None
        power *= base
      else:
        return None
    return number

  def numeric_value(self) -> int:
    return Literal.__value(self.raw)

  def description(self) -> str:
    return f"literal '{self.raw}'"
# Token types

# Parser workers
# NullObject design pattern
class Worker(object):
  def add_pending_label(self, label: LabelDeclaration) -> None: pass
  def flush_pending_labels(self) -> None: pass
  def write(self, token: Token) -> None: pass
  def write_dereferenced_label(self, label: LabelReference) -> None: pass

class LabelLister(Worker):
  def __init__(self) -> None:
    # A double-ended queue for storing names of labels
    # that need to have their memory positions calculated before
    # they can be added to 'labels'.
    self.__pending_labels = deque[LabelDeclaration]()
    self.__labels = dict[str, int]() # Label and its memory address.
    self.__warnings = deque[str]()
    # Start counting translated memory words from 0.
    self.__memory_word_index = 0

  def add_pending_label(self, label: LabelDeclaration) -> None:
    self.__pending_labels.append(label)

  def flush_pending_labels(self) -> None:
    # Set pending labels to the current word address (index)
    # and clear pending label queue.
    for label in self.__pending_labels:
      name = label.name()
      if name in self.__labels:
        self.__warnings.append(
          "Warning: Label '{}' redeclared in line {}, column {}."
          .format(name, label.line, label.column))
      # Redeclaration produces a warning and overwrites the label's position.
      self.__labels[name] = self.__memory_word_index
    self.__pending_labels.clear()
    self.__memory_word_index += 1

  def get_labels(self) -> dict[str, int]:
    return self.__labels
  
  def get_warnings(self) -> deque[str]:
    return self.__warnings

class Translator(Worker):
  def __init__(self, labels: dict[str, int], word_size: int,
    writer: Writer) -> None:
    self.__labels = labels
    self.__errors = deque[str]()

    self.__buffer = bytearray(0 for n in range(word_size))
    self.__buffer_index = 0

    self.__writer = writer

  def write(self, token: Token) -> None:
    self.__write_number(token.numeric_value(), token.bit_count())

  def write_dereferenced_label(self, label: LabelReference) -> None:
    name = label.name()
    if name not in self.__labels:
      self.__errors.append(
        "Error: Undeclared label '{}' referenced in line {}, column {}."
        .format(name, label.line, label.column))
    else:
      self.__write_number(self.__labels[name], label.bit_count())

  def __write_number(self, number: int, bit_count: int) -> None:
    for shift in range(bit_count - 1, -1, -1): # Highest bit first.
      self.__write_bit((number >> shift) & 1)

  def __write_bit(self, bit: int) -> None:
    buffer = self.__buffer
    index = self.__buffer_index

    bit &= 1 # Clear all bits except the lowest.
    buffer[index] = bit

    if index >= len(buffer) - 1: # Flush the word in buffer.
      self.__writer.write_word(self.__buffer)
      index = 0
    else:
      index += 1

    self.__buffer_index = index

  def get_errors(self) -> deque[str]:
    return self.__errors
# Parser workers

class Parser(object):
  # Parser states
  class State(object):
    # Single '_' means protected method access modifier.
    def _error_unexpected(self, token: Token) -> str:
      return ("Error: Unexpected {} in line {}, column {}."
        .format(token.description(), token.line, token.column))

  class Initial(State):
    def parse_token(self, ctx: Parser, token: Token) -> str:
      # INITIAL
      match token: # Operation dependent on token type.
        case Newline(): # Do not change state.
          pass
        case LabelDeclaration(): # Do not change state.
          ctx.worker.add_pending_label(token)
        case RegisterInstruction():
          ctx.state = Parser.RegisterInstruction()
          ctx.worker.write(token)
        case ImmediateInstruction():
          ctx.state = Parser.ImmediateInstruction()
          ctx.worker.write(token)
        case NumericValue():
          ctx.state = Parser.NumericValue()
          ctx.worker.flush_pending_labels()
          # 'Is' compares only references.
          # 'LabelReference' is a metaclass and a singleton.
          # 'LabelReference' identifier used in code works as a
          # reference to the sole instance of 'LabelReference'
          # metaclass.
          if isinstance(token, LabelReference):
            ctx.worker.write_dereferenced_label(token)
          else: # isinstance(token, Literal):
            ctx.worker.write(token)
        case _:
          return self._error_unexpected(token)

  class RegisterInstruction(State):
    def __init__(self) -> None:
      self.__substate = 0

    def parse_token(self, ctx: Parser, token: Token) -> str:
      operations = [
        self.__parse_1st_register,
        self.__parse_2nd_register,
        self.__parse_newline
      ]
      error = operations[self.__substate](ctx, token)
      if error is not None:
        return error
      self.__substate += 1

    def __parse_1st_register(self, ctx: Parser, token: Token) -> str:
      # After register instruction name
      if not isinstance(token, Register):
        return self._error_unexpected(token)
      ctx.worker.write(token)

    def __parse_2nd_register(self, ctx: Parser, token: Token) -> str:
      # After 1 operand (register)
      if not isinstance(token, Register):
        return self._error_unexpected(token)
      ctx.worker.flush_pending_labels()
      ctx.worker.write(token)

    def __parse_newline(self, ctx: Parser, token: Token) -> str:
      # After 2 operands (registers)
      if not isinstance(token, Newline):
        return self._error_unexpected(token)
      ctx.state = Parser.Initial()

  class ImmediateInstruction(State):
    def __init__(self) -> None:
      self.__substate = 0

    def parse_token(self, ctx: Parser, token: Token) -> str:
      operations = [
        self.__parse_register,
        self.__parse_newline,
        self.__parse_numeric_value
      ]
      error = operations[self.__substate](ctx, token)
      if error is not None:
        return error

    def __parse_register(self, ctx: Parser, token: Token) -> str:
      # After immediate instruction name
      if not isinstance(token, Register):
        return self._error_unexpected(token)
      ctx.worker.flush_pending_labels()
      ctx.worker.write(token)
      # The processor ignores the second register code so print R0 there.
      first_register_code = next(iter(Register.CODES.keys()))
      ctx.worker.write(Register(
        Token(first_register_code, token.line, token.column)))
      self.__substate += 1

    def __parse_newline(self, ctx: Parser, token: Token) -> str:
      # After 1 operand (register)
      if not isinstance(token, Newline):
        return self._error_unexpected(token)
      self.__substate += 1

    def __parse_numeric_value(self, ctx: Parser, token: Token) -> str:
      # After 1 operand and newline
      match token:
        case Newline(): # Skip multiple newlines. Do not change state.
          pass
        case LabelDeclaration(): # Do not change state.
          ctx.worker.add_pending_label(token)
        case NumericValue():
          ctx.state = Parser.NumericValue()
          ctx.worker.flush_pending_labels()
          if isinstance(token, LabelReference):
            ctx.worker.write_dereferenced_label(token)
          else:
            ctx.worker.write(token)
        case _:
          return self._error_unexpected(token)

  # Data words, not to be executed by the processor.
  class NumericValue(State):
    def parse_token(self, ctx: Parser, token: Token) -> str:
      if not isinstance(token, Newline):
        return self._error_unexpected(token)
      ctx.state = Parser.Initial()
  # Parser states

  def parse(self, source: TextIOWrapper, worker: Worker) -> str:
    self.worker = worker
    self.state = Parser.Initial()

    source.seek(0, 0)
    tokenizer = self.__tokenize(source)
    # Traverse the source code token by token with a state machine.
    for unclassified_token in tokenizer:
      token = self.__classify_token(unclassified_token)
      if token is None: # Unrecognized token type.
        ut = unclassified_token
        return ("Error: Unrecognized token '{}' in line {}, column {}."
          .format(ut.raw, ut.line, ut.column))

      error = self.state.parse_token(self, token)
      if error is not None:
        return error
    return None

  def __classify_token(self, token: Token) -> Token:
    types = [
      Newline,
      LabelDeclaration,
      RegisterInstruction,
      ImmediateInstruction,
      Register,
      LabelReference,
      Literal
    ]
    for t in types:
      # Equivalent to C#: if ((Newline.TryParse(token, out ret)) != false)
      if (ret := t.try_parse(token)) is not None: return ret
    return None

  # This function is a coroutine (https://en.wikipedia.org/wiki/Coroutine)
  # because it is paused using 'yield' and resumed by being called again.
  # Returns an unclassified token.
  def __tokenize(self, source: TextIOWrapper) -> Token:
    states = SimpleNamespace()
    states.WHITESPACE = 0
    states.NEWLINE = 1
    states.COMMENT = 2
    states.TEXT = 3

    state = states.WHITESPACE
    text_token = None
    last_newline_char = None

    line, column, token_start = 1, 0, 0

    def start_text_token(first_char: str) -> None:
      nonlocal state, text_token, token_start
      state = states.TEXT
      text_token = first_char # Start a new text token.
      token_start = column

    def start_newline_token() -> None:
      nonlocal state, token_start
      state = states.NEWLINE
      token_start = column

    def text() -> Token:
      return Token(text_token, line, token_start)

    def newline() -> Token:
      nonlocal line, column
      ret = Token("\n", line, token_start)
      line += 1
      column = 0
      return ret

    # Traverse the source code character by character with a state machine.
    # Complete tokens are separated with whitespace characters.
    # Yield on every complete token but do not notify the caller about
    # comment tokens because it will ignore them anyway.
    while True:
      char = source.read(1)
      if not char: # Reached end of the source.
        # Final 'return'.
        match state:
          case states.WHITESPACE:
            # Return a newline token for an unterminated "\r".
            if last_newline_char == "\r":
              # Firstly 'yield', because the user of 'tokenize' generator
              # (e.g. 'for unclassified_token in tokenizer:')
              # breaks on returned value, only processes yielded values.
              yield newline()
            # else last_newline_char == "\n" -
            # A newline token for "\n" has already been returned.
            # 'None' returned by the generator breaks a 'for in' loop.
            return None
          case states.TEXT:
            yield text()
        return None

      column += 1
      if char in "\r\n": # Newline (separator) token character met.
        match state:
          case states.WHITESPACE:
            start_newline_token()
            if char == "\n":
              yield newline()
            # else char == "\r" - Do nothing and wait for potential "\n".
            last_newline_char = char
          case states.NEWLINE:
            start_newline_token()
            if last_newline_char == "\n":
              if char == "\n":
                yield newline() # "\n\n" met.
              # else char == "\r" - Do nothing and wait for potential "\n".
            else: # last_newline_char == "\r"
              # "\r\n" or "\r\r" met.
              # Return a newline token ("\n") only once for the entire "\r\n"
              # or for just the first '\r' from "\r\r".
              yield newline()
            last_newline_char = char
          case states.COMMENT:
            start_newline_token()
            if char == "\n":
              yield newline()
            last_newline_char = char
          case states.TEXT:
            # With 'yield' we can pause and then resume this function
            # coming back to this line and context (variables' values)
            # the next time we call this function.
            yield text() # End text token.
            start_newline_token()
            if char == "\n":
              yield newline()
            # else: # char == "\r" - Do nothing and wait for potential "\n".
            last_newline_char = char

      # Unicode has many whitespace characters
      # but we handle only the common U+0020.
      elif char in " ": # Whitespace token character met.
        match state:
          case states.WHITESPACE:
            pass
          case states.NEWLINE:
            if last_newline_char == "\r":
              yield newline()
            state = states.WHITESPACE
          case states.COMMENT:
            pass # A comment ends only at newline character.
          case states.TEXT:
            yield text()
            state = states.WHITESPACE

      elif char == ";": # Comment token beginning met.
        match state:
          case states.WHITESPACE:
            state = states.COMMENT
          case states.NEWLINE:
            if last_newline_char == "\r":
              yield newline()
            state = states.COMMENT
          case states.COMMENT:
            pass
          case states.TEXT:
            yield text()
            state = states.COMMENT

      else: # Text token character met.
        match state:
          case states.WHITESPACE:
            start_text_token(char)
          case states.NEWLINE:
            if last_newline_char == "\r":
              yield newline()
            start_text_token(char)
          case states.COMMENT:
            pass
          case states.TEXT:
            text_token += char # Append the character to the current text token.

# NullObject
class Writer(object):
  def write_word(self, word: bytearray) -> None:
    pass

# Does not write binary words to any target but only counts them.
class WordCounter(Writer):
  def __init__(self) -> None:
    self.__written_words = 0

  def write_word(self, word: bytearray) -> None:
    # Count the words but do not write them.
    self.__written_words += 1

  def get_written_words(self) -> int:
    return self.__written_words

# Writes binary words to stdout.
class TextIOWriter(Writer):
  def __init__(self, target: TextIO) -> None:
    self.__target = target

  def write_word(self, word: bytearray) -> None:
    for b in word:
      self.__target.write(chr(ord("0") + b))
    self.__target.write("\n")

# Writes binary words to SRAM.v.
# This class is designed to work with NanoProcessor/src/SRAM.v file present
# in this repository.
class SRAMvWriter(Writer):
  def __init__(self, target: TextIOWrapper, word_size: int,
    words_in_buffer: int, prefix: Command, suffix: Command) -> None:
    self.__target = target
    self.__prefix = prefix
    self.__suffix = suffix

    self.__word_size = word_size
    # Number of word_size-bit words in one buffer.
    self.__buffer = bytearray(0 for i in range(word_size * words_in_buffer))
    self.__buffer_index = self.__max_index()
    self.__written_words = 0

  def __max_index(self) -> int:
    return len(self.__buffer) - self.__word_size

# Example for 9-bit WORD_SIZE.
# |buffer[0]                                                               buffer[length-1]|
# 0b001     0b000     0b001     0b100     ... 0b01_0000000 mvi R1  -   1         mvi R0  - |
# |MSB                                                     |MSB                            |
# |       |LSB                                               |LSB                          |
# 000000001 000000000 000000001 000000100 ... 010000000    001 001 000 000000001 001 000 000
# Divide into groups of 9 bits.
# 000000001 000000000 000000001 000000100 ... 010000000 001001000 000000001 001000000
# Divide into groups of 4 bits.
# 0000 0000 1000 0000 0000 0000 0010 0000 0100 ... 0100 0000 0001 0010 0000 0000 0010 0100 0000
# Convert groups to hexadecimal digits.
# 0 0 8 0 0 0 2 0 4 ... 4 0 1 2 0 0 2 4 0
  def write_word(self, word: bytearray) -> None:
    if len(word) != self.__word_size:
      raise ValueError("Word must be {} bits long.".format(self.__word_size))

    buffer = self.__buffer
    index = self.__buffer_index

    # Write words beginning at the highest index of the buffer.
    buffer[index : index + self.__word_size] = word

    # If already at the lowest index of the buffer.
    if index <= 0:
      self.__flush_buffer()
      index = self.__max_index()
    else:
      index -= self.__word_size

    self.__written_words += 1
    self.__buffer_index = index

  def __flush_buffer(self) -> None:
    buffer = self.__buffer
    length = len(buffer)

    # Convert 4-bit groups to hexadecimal digits.
    self.__start_line()
    for i in range(0, length, 4):
      decimal = 0
      multiplier = 8 # 2^(4-1)
      for j in range(i, i+4, 1):
        decimal += buffer[j] * multiplier
        multiplier //= 2 # Integer division
      self.__write_hex(decimal)
    self.__end_line()
  
  def __start_line(self) -> None:
    self.__target.write(self.__prefix.execute(self.__written_buffers()))

  def __written_buffers(self) -> None:
    return self.__written_words // (len(self.__buffer) // self.__word_size)

  def __write_hex(self, decimal: int) -> None:
    self.__target.write(self.__int_to_hex_char(decimal))

  def __int_to_hex_char(self, number: int) -> str:
    if number < 10:
      return chr(ord("0") + number)
    return chr(ord("A") + (number - 10))

  def __end_line(self) -> None:
    self.__target.write(self.__suffix.execute())

  def pad(self, total_words) -> None:
    # Pad with zeros if self.__written_words < total_words.
    for b in range(0, total_words - self.__written_words):
      self.write_word(bytearray(0 for n in range(0, self.__word_size)))

class Assembler(object):
  def __init__(self, source: TextIOWrapper, word_size: int) -> None:
    self.__source = source
    self.__word_size = word_size 

  def __parse_with_worker(self, worker: Worker) -> str:
    return Parser().parse(self.__source, worker)

  def validate_syntax_and_list_labels(self) -> int:
    lister = LabelLister()
    # Validate the source assembly code syntax and locate label declarations.
    error = self.__parse_with_worker(lister)
    if error is not None: # Code has at least one syntax error.
      print(error)
      return -1

    # Code has no syntax errors. Notify about label redeclarations, if any.
    for warning in lister.get_warnings():
      print(warning)

    self.__labels = lister.get_labels()
    return 0

  def validate_label_references(self) -> int:
    translator = Translator(self.__labels, self.__word_size, Writer())
    # Check if no undeclared labels are referenced.
    self.__parse_with_worker(translator)
    # Source code should have been checked for syntax errors
    # in 'validate_syntax_and_list_labels' so do not check again.

    # Notify about undeclared labels, if any.
    errors = translator.get_errors()
    if len(errors) > 0:
      for error in errors:
        print(error)
      return -1

    # No undeclared labels are referenced.
    return 0

  def validate_code_size(self, word_limit: int) -> int:
    counter = WordCounter()
    translator = Translator(self.__labels, self.__word_size, counter)
    # Check if the assembled binary code is not too long.
    self.__parse_with_worker(translator)

    w_s = self.__word_size
    counted_words = counter.get_written_words()
    if counted_words > word_limit:
      print("Error: Assembled source code needs "
        f"{counted_words}x{w_s}-bit words ({counted_words*w_s} bits) "
        "bits but SRAM.v capacity is only "
        f"{word_limit}x{w_s}-bit words ({word_limit*w_s} bits).")
      return -1

    return 0

  def write_output(self, writer: Writer) -> None:
    translator = Translator(self.__labels, self.__word_size, writer)
    # Write instructions and numeric values translated to binary words
    # to output.
    self.__parse_with_worker(translator)

# Command design pattern
class Command(object):
  def __init__(self, function_) -> None:
    self.__function = function_

  def execute(self, parameter = None) -> object:
    return self.__function(parameter)

def assemble_to_sram_v_file(source: TextIOWrapper, target_path: str) -> int:
  # In SRAM.v there are 4 lines
    # defparam spx9_inst_0.INIT_RAM_0{0-3} = 288'h{72 hex digits};
  # Line 'defparam spx9_inst_0.INIT_RAM_00 = 288'h{72 hex digits};'
  # is at position 1217.
  first_init_ram_position = 1217
  lines = 4
  hex_digits = 72 # SRAM module has 128 9-bit words.
  word_size = 9 # The target processor's word size in bits
  # n in INIT_RAM_n must be in range <0, 63>. This information comes from
  # '<Gowin_V1.9.8.03_Education directory>/IDE/bin/prim_syn.v'
  # file containing 'headers' of the IP cores available in Gowin FPGA Designer.
  prefix = ("defparam spx9_inst_0.INIT_RAM_{:02X} = " +
    "{}".format(hex_digits * 4) + "'h")
  suffix = (";\n")

  if not os.path.isfile(target_path):
    print("File '{target_path}' does not exist.")
    return -1

  with open(target_path, "r+", encoding="utf_8") as file:
    file.seek(first_init_ram_position)

    for line_index in range(lines):
      line = file.readline()

      formatted_prefix = prefix.format(line_index)
      if not line.startswith(formatted_prefix):
        print(f"Error: Line '{line}' in file '{target_path}' does not start "
          f"with '{formatted_prefix}'.")
        return -2

      if not line.endswith(suffix):
        print(f"Error: Line '{line}' in file '{target_path}' does not end "
          f"with '{suffix}'.")
        return -3

      # ... 288'h000 ... 000;
      #          ^line[len(formatted_prefix)]
      if len(line) - len(suffix) - len(formatted_prefix) != hex_digits:
        print(f"Error: Line '{line}' in file '{target_path}' does not contain "
          f"exactly '{hex_digits}' hexadecimal digits.")
        return -4

    line_size = (hex_digits * 4) // word_size

    asm = Assembler(source, word_size)
    if asm.validate_syntax_and_list_labels() != 0:
      return -5
    if asm.validate_label_references() != 0:
      return -6
    if asm.validate_code_size(lines * line_size) != 0:
      return -7

    file.seek(first_init_ram_position)
    writer = SRAMvWriter(file, word_size, line_size,
      Command(lambda line_index: prefix.format(line_index)),
      Command(lambda _: suffix)) # Ignore command parameter.
    asm.write_output(writer)
    writer.pad(line_size * lines)
    file.write("\nendmodule //SRAM\n")

  return 0

def assemble_to_stdout(source: TextIOWrapper) -> None:
  asm = Assembler(source, 9)
  if asm.validate_syntax_and_list_labels() != 0:
    return -1
  if asm.validate_label_references() != 0:
    return -2

  asm.write_output(TextIOWriter(sys.stdout))

  return 0

def parse_commandline_arguments():
  # https://stackoverflow.com/a/30493366
  # https://docs.python.org/3/library/argparse.html
  parser = argparse.ArgumentParser(prog="NanoAssembler",
    description="Translate a file written in NanoAssembly language "
    "to NanoProcessor machine (binary) code.",
    add_help=False) # Disable the automatic addition of '-h' argument.

  parser.add_argument("source", type=str, help="Path to a text file written in "
    "NanoAssembly language.")

  parser.add_argument('-h', action='help', default=argparse.SUPPRESS,
    help='Show this help message and exit.')

  parser.add_argument("-e", type=str, dest="source_encoding",
    help="Specify encoding of the source file. See 'codecs' Python module "
    "for the list of supported encodings "
    "(https://docs.python.org/3/library/codecs.html#standard-encodings). "
    "If source encoding is not specified, NanoAssembler attempts to determine "
    "it using 'chardet' Python module as long as the user has it installed. "
    "Do not use automatic encoding detection for big files that cannot "
    "entirely fit in Python script's memory. Such a program probably "
    "would not fit in NanoProcessor's memory anyway.")

  parser.add_argument("-o", type=str, dest="target",
    help="Overwrite initial memory content in specified SRAM module "
    "Verilog file (SRAM.v). If this argument is not used, "
    "the machine code is written to stdout.")

  # An optional positional argument can be used instead of -o.
  # parser.add_argument("target", type=str, nargs="?",
  # help="Initial memory content in this SRAM module file will be overwritten.")

  return parser.parse_args()

def encoding_supported(encoding):
  try:
    codecs.lookup(encoding)
  except LookupError:
    return False
  return True

def main():
  args = parse_commandline_arguments()

  if not os.path.isfile(args.source):
    print("File '{}' does not exist.".format(args.source))
    return -1

  # Check if 'source_encoding' parameter is specified.
  # Alternatively: if hasattr(args, "source_encoding"):
  if args.source_encoding is not None:
    if not encoding_supported(args.source_encoding):
      print("Source encoding '{}' is not supported."
        .format(args.source_encoding))
      return -2
    # Specified source encoding is supported by 'codecs'.
    source_encoding = args.source_encoding
  else:
    # Open source file only to determine its encoding.
    # Only for small files that can entirely fit in program's memory.
    with open(args.source, "rb") as source:
      binary_data = source.read()

      # Exit if 'chardet' is unavailable.
      try:
        import chardet
      except:
        print("'Chardet' library is unavailable. Install it or manually "
          "specify source encoding.")
        return -3

      detected_encoding = chardet.detect(binary_data)["encoding"]
      if not encoding_supported(detected_encoding):
        print("Detected source encoding '{}' is not supported."
          .format(detected_encoding))
        return -4
      # Detected source encoding is supported by 'codecs'.
      print("Detected source encoding '{}'.".format(detected_encoding))
      source_encoding = detected_encoding

  with open(args.source, "r", encoding=source_encoding) as source:
    # Check if 'target' parameter is specified.
    if args.target is not None:
      assemble_to_sram_v_file(source, args.target)
    else:
      assemble_to_stdout(source)

  return 0

# Allow running NanoAssembler as a script but not when it is imported
# as a module.
if __name__ == "__main__":
  # Return exit code from 'main' function.
  sys.exit(main())
