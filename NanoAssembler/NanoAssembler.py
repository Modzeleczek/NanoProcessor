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
  # Consider this abstract method.
  def describe(self) -> str:
    raise NotImplementedError("Please implement this method")

class Newline(Token):
  def try_parse(token: str) -> Newline:
    if token == "\n":
      return Newline()
    return None

  def describe(self) -> str:
    return "newline"

class LabelDeclaration(Token):
  def __init__(self, raw: str) -> None:
    self.__raw = raw
    # For the index of the line in which the declaration was met.
    self.__line_index = None

  def try_parse(token: str) -> LabelDeclaration:
    if token.endswith(":"):
      return LabelDeclaration(token) # Do not skip ":".
    return None

  def describe(self) -> str:
    return "label description token '{}'".format(self.__raw)

  def raw(self) -> str:
    return self.__raw

  def name(self) -> str:
    return self.__raw[:-1] # Skip ":".

  def get_line_index(self) -> None: # Getter
    return self.__line_index

  def set_line_index(self, value: int) -> None: # Setter
    self.__line_index = value

class Instruction(Token):
  def __init__(self, raw: str) -> None:
    self.__raw = raw

  def raw(self) -> str:
    return self.__raw

  def code(self) -> int:
    return self.CODES[self.__raw]

class RegisterInstruction(Instruction):
  CODES = { "mv":0, "add":2, "sub":3, "ld":4, "st":5, "mvnz":6 }

  def __init__(self, raw: str) -> None:
    super().__init__(raw)

  def try_parse(token: str) -> RegisterInstruction:
    codes = RegisterInstruction.CODES
    if token in codes:
      return RegisterInstruction(token)
    return None

  def describe(self) -> str:
    return "register instruction token '{}'".format(self.__raw)

class ImmediateInstruction(Instruction):
  # 'mvi' is 'immediate' instruction whose second operand must
  # be specified immediately after the instruction word.
  CODES = { "mvi":1 }

  def __init__(self, raw: str) -> None:
    super().__init__(raw)

  def try_parse(token: str) -> ImmediateInstruction:
    codes = ImmediateInstruction.CODES
    if token in codes:
      return ImmediateInstruction(token)
    return None

  def describe(self) -> str:
    return "immediate instruction token '{}'".format(self.__raw)

class Register(Instruction):
  CODES = { "R0":0, "R1":1, "R2":2, "R3":3, "R4":4, "R5":5, "R6":6, "PC":7 }

  def __init__(self, raw: str) -> None:
    super().__init__(raw)

  def try_parse(token: str) -> Register:
    codes = Register.CODES
    if token in codes:
      return Register(token)
    return None

  def describe(self) -> str:
    return "register token '{}'".format(self.__raw)

class Literal(Token): pass

class LabelReference(Literal):
  def __init__(self, raw: str) -> None:
    self.__raw = raw

  def try_parse(token: str) -> LabelReference:
    if token.startswith(":"):
      return LabelReference(token) # Do not skip ":".
    return None

  def describe(self) -> str:
    return "label reference literal token '{}'".format(self.__raw)

  def raw(self) -> str:
    return self.__raw

  def name(self) -> str:
    return self.__raw[1:] # Skip ":".

class NumericLiteral(Literal):
  def __init__(self, raw: str) -> None:
    self.__raw = raw

  def try_parse(token: str) -> NumericLiteral:
    if NumericLiteral.__value(token) is not None:
      return NumericLiteral(token)
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

    return NumericLiteral.str_to_int(digits, base)

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

  def describe(self) -> str:
    return "numeric literal token '{}'".format(self.__raw)

  def raw(self) -> str:
    return self.__raw

  def value(self) -> int:
    return NumericLiteral.__value(self.__raw)
# Token types

# Parser workers
class LabelLister(object):
  def __init__(self) -> None:
    # A double-ended queue for storing names of labels
    # that need to have their memory positions calculated before
    # they can be added to 'labels'.
    self.__pending_labels = deque[LabelDeclaration]()
    self.__labels = dict[str, int]() # Label and its memory address.
    self.__warnings = deque[str]()
    # Start counting translated memory words from 0.
    self.__memory_word_index = 0

  def add_pending_label(self, label: LabelDeclaration, line_index: int) -> None:
    label.set_line_index(line_index)
    self.__pending_labels.append(label)

  def flush_pending_labels(self) -> None:
    # Set pending labels to the current word address (index)
    # and clear pending label queue.
    for label in self.__pending_labels:
      label_name = label.name()
      if label_name in self.__labels:
        self.__warnings.append("Warning: Label '{}' redeclared in line {}."
          .format(label_name, label.get_line_index()))
      # Redeclaration produces a warning and overwrites the label's position.
      self.__labels[label_name] = self.__memory_word_index
    self.__pending_labels.clear()
    self.__memory_word_index += 1

  def get_labels(self) -> dict[str, int]:
    return self.__labels
  
  def get_warnings(self) -> deque[str]:
    return self.__warnings

# NullObject design pattern
class NullLabelLister(LabelLister):
  def __init__(self) -> None:
    pass

  def add_pending_label(self, label: LabelDeclaration, line_index: int) -> None:
    pass

  def flush_pending_labels(self) -> None:
    pass

class LabelReferencer(object):
  def __init__(self, labels: dict[str, int]) -> None:
    self.__labels = labels

  def get_label_position(self, name: str) -> int:
    # Return 'None' if label does not exist.
    if name in self.__labels:
      return self.__labels[name]
    return None

class NullLabelReferencer(LabelReferencer):
  def __init__(self) -> None:
    pass

  def get_label_position(self, name: str) -> int:
    return -1

class Writer(object):
  def __init__(self, target: TextIO | TextIOWrapper) -> None:
    self.__target = target

  def print(self, number: int, bit_count: int, end: str = "") -> None:
    bit_string = ""
    for b in range(0, bit_count):
      bit_string = str(number % 2) + bit_string
      number //= 2
    self.__target.write(bit_string + end)

class NullWriter(Writer):
  def __init__(self) -> None:
    pass

  def print(self, number: int, bit_count: int, end: str = "") -> None:
    pass
# Parser workers

class Assembler(object):
  def assemble(self, source: TextIOWrapper,
    target: TextIO | TextIOWrapper) -> None:
    # Validate the source assembly code.
    # Locate label declarations.
    label_lister = LabelLister()
    error = self.__parse(source,
      label_lister,
      NullLabelReferencer(),
      NullWriter())
    for warning in label_lister.get_warnings():
      print(warning)

    if error is not None: # Code has an error.
      print(error)

    else: # Code is valid.
      # Translate instructions and literals (numeric values) to binary words.
      self.__parse(source,
        NullLabelLister(),
        LabelReferencer(label_lister.get_labels()),
        Writer(target))
      # Do not check for warnings and an error again
      # because code was already validated.

  # Pass a base LabelLister, LabelReferencer or Writer object
  # with empty method definitions to disable the corresponding feature.
  def __parse(self, source: TextIOWrapper,
    label_lister: LabelLister,
    label_referencer: LabelReferencer,
    writer: Writer) -> str:
    states = SimpleNamespace()
    states.INITIAL = 0
    # states.LABEL_DECLARATION # This state only complicates the state machine.
    states.REGISTER_INSTRUCTION = 1
    states.REGISTER_INSTRUCTON_1_OPERAND = 2
    states.REGISTER_INSTRUCTON_2_OPERANDS = 3
    states.IMMEDIATE_INSTRUCTION = 4
    states.IMMEDIATE_INSTRUCTION_1_OPERAND = 5
    states.IMMEDIATE_INSTRUCTION_1_OPERAND_NEWLINE = 6
    # Data words, not to be executed by the processor.
    states.LITERAL = 7

    state = states.INITIAL

    # Start counting source code lines from 1.
    line_index = 1

    def unexpected_token(token: Token) -> str:
      return "Error: Unexpected {} in line {}."\
        .format(token.describe(), line_index)

    def undeclared_label(label: LabelReference) -> str:
      return "Error: Reference to undeclared label '{}' in line {}."\
        .format(label.name(), line_index)

    source.seek(0, 0)
    tokenizer = self.__tokenize(source)
    # Traverse the source code token by token with a state machine.
    for unclassified_token in tokenizer:
      token = self.__classify_token(unclassified_token)
      if token is None: # Unrecognized token type.
        return "Error: Unrecognized token '{}' in line {}."\
          .format(unclassified_token, line_index)

      match state:
        case states.INITIAL:
          match token: # Operation dependent on token type.
            case Newline(): # Do not change state.
              line_index += 1
            case LabelDeclaration(): # Do not change state.
              label_lister.add_pending_label(token, line_index)
            case RegisterInstruction():
              state = states.REGISTER_INSTRUCTION
              writer.print(token.code(), 3)
            case ImmediateInstruction():
              state = states.IMMEDIATE_INSTRUCTION
              writer.print(token.code(), 3)
            case Literal():
              state = states.LITERAL
              label_lister.flush_pending_labels()
              # 'Is' compares only references.
              # 'LabelReference' is a metaclass and a singleton.
              # 'LabelReference' identifier used in code works as a
              # reference to the sole instance of 'LabelReference'
              # metaclass.
              if isinstance(token, LabelReference):
                position = label_referencer.get_label_position(token.name())
                if position is not None:
                  writer.print(position, 9, "\n")
                else:
                  return undeclared_label(token)
              else: # isinstance(token, NumericLiteral):
                writer.print(token.value(), 9, "\n")
            case _:
              return unexpected_token(token)

        # Register instruction
        case states.REGISTER_INSTRUCTION:
          match token:
            case Register():
              state = states.REGISTER_INSTRUCTON_1_OPERAND
              writer.print(token.code(), 3)
            case _:
              return unexpected_token(token)

        case states.REGISTER_INSTRUCTON_1_OPERAND:
          match token:
            case Register():
              state = states.REGISTER_INSTRUCTON_2_OPERANDS
              label_lister.flush_pending_labels()
              writer.print(token.code(), 3, "\n")
            case _:
              return unexpected_token(token)
          
        case states.REGISTER_INSTRUCTON_2_OPERANDS:
          match token:
            case Newline():
              state = states.INITIAL
              line_index += 1
            case _:
              return unexpected_token(token)
        # Register instruction

        # Immediate instruction
        case states.IMMEDIATE_INSTRUCTION:
          match token:
            case Register():
              state = states.IMMEDIATE_INSTRUCTION_1_OPERAND
              label_lister.flush_pending_labels()
              writer.print(token.code(), 3)
              writer.print(0, 3, "\n")
            case _:
              return unexpected_token(token)

        case states.IMMEDIATE_INSTRUCTION_1_OPERAND:
          match token:
            case Newline():
              state = states.IMMEDIATE_INSTRUCTION_1_OPERAND_NEWLINE
              line_index += 1
            case _:
              return unexpected_token(token)

        case states.IMMEDIATE_INSTRUCTION_1_OPERAND_NEWLINE:
          match token:
            case Newline():
              # Skip multiple newlines. Do not change state.
              line_index += 1
            case LabelDeclaration():
              # Do not change state.
              label_lister.add_pending_label(token, line_index)
            case Literal():
              state = states.LITERAL
              label_lister.flush_pending_labels()
              if isinstance(token, LabelReference):
                  position = label_referencer.get_label_position(token.name())
                  if position is not None:
                    writer.print(position, 9, "\n")
                  else:
                    return undeclared_label(token)
              else:
                writer.print(token.value(), 9, "\n")
            case _:
              return unexpected_token(token)
        # Immediate instruction

        case states.LITERAL:
          match token:
            case Newline():
              state = states.INITIAL
              line_index += 1
            case _:
              return unexpected_token(token)
    # for
    return None

  def __classify_token(self, token: str) -> Token:
    # Equivalent to C#: if ((Newline.TryParse(token, out ret)) != false)
    if (ret := Newline.try_parse(token)) is not None: return ret
    if (ret := LabelDeclaration.try_parse(token)) is not None: return ret
    if (ret := RegisterInstruction.try_parse(token)) is not None: return ret
    if (ret := ImmediateInstruction.try_parse(token)) is not None: return ret
    if (ret := Register.try_parse(token)) is not None: return ret
    if (ret := LabelReference.try_parse(token)) is not None: return ret
    if (ret := NumericLiteral.try_parse(token)) is not None: return ret
    return None

  # This function is a coroutine (https://en.wikipedia.org/wiki/Coroutine)
  # because it is paused using 'yield' and resumed by being called again.
  def __tokenize(self, source: TextIOWrapper) -> str:
    states = SimpleNamespace()
    states.WHITESPACE = 0
    states.NEWLINE = 1
    states.COMMENT = 2
    states.TEXT = 3

    state = states.WHITESPACE
    text_token = None
    last_newline_char = None
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
              yield "\n"
            # else last_newline_char == "\n" -
            # A newline token for "\n" has already been returned.
            # 'None' returned by the generator breaks a 'for in' loop.
            return None
          case states.TEXT:
            yield text_token
        return None

      elif char in "\r\n": # Newline (separator) token character met.
        match state:
          case states.WHITESPACE:
            state = states.NEWLINE
            if char == "\n":
              yield "\n"
            # else char == "\r" - Do nothing and wait for potential "\n".
            last_newline_char = char
          case states.NEWLINE:
            if last_newline_char == "\n":
              if char == "\n":
                yield "\n" # "\n\n" met.
              # else char == "\r" - Do nothing and wait for potential "\n".
            else: # last_newline_char == "\r"
              # "\r\n" or "\r\r" met.
              # Return a newline token ("\n") only once for the entire "\r\n"
              # or for just the first '\r' from "\r\r".
              yield "\n"
            last_newline_char = char
          case states.COMMENT:
            state = states.NEWLINE
            if char == "\n":
              yield "\n"
            last_newline_char = char
          case states.TEXT:
            # With 'yield' we can pause and then resume this function
            # coming back to this line and context (variables' values)
            # the next time we call this function.
            yield text_token # End text token.
            state = states.NEWLINE
            if char == "\n":
              yield "\n"
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
              yield "\n"
            state = states.WHITESPACE
          case states.COMMENT:
            pass # A comment ends only at newline character.
          case states.TEXT:
            yield text_token
            state = states.WHITESPACE

      elif char == ";": # Comment token beginning met.
        match state:
          case states.WHITESPACE:
            state = states.COMMENT
          case states.NEWLINE:
            if last_newline_char == "\r":
              yield "\n"
            state = states.COMMENT
          case states.COMMENT:
            pass
          case states.TEXT:
            yield text_token
            state = states.COMMENT

      else: # Text token character met.
        match state:
          case states.WHITESPACE:
            state = states.TEXT
            text_token = char # Start a new text token.
          case states.NEWLINE:
            if last_newline_char == "\r":
              yield "\n"
            state = states.TEXT
            text_token = char
          case states.COMMENT:
            pass
          case states.TEXT:
            text_token += char # Append the character to the current text token.

def parse_commandline_arguments():
  # https://stackoverflow.com/a/30493366
  # https://docs.python.org/3/library/argparse.html
  parser = argparse.ArgumentParser(prog="NanoAssembler",
    description="Translate a file written in NanoProcessor assembly language "
    "to NanoProcessor machine (binary) language.")

  parser.add_argument("source", type=str, help="File in NanoProcessor "
    "assembly language.")

  parser.add_argument("-e", type=str, dest="source_encoding",
    help="Specify encoding of the source file. See 'codecs' module "
    "for the list of supported encodings "
    "(https://docs.python.org/3/library/codecs.html#standard-encodings). "
    "If source encoding is not specified, NanoAssembler attempts to determine "
    "it using 'chardet' library as long as the user has it installed. "
    "Do not use automatic encoding detection for big files that cannot entirely "
    "fit in program's memory. Such a program would not fit in NanoProcessor's "
    "memory anyway.")

  parser.add_argument("-o", type=str, dest="target",
    help="Overwrite initial memory content in specified SRAM module Verilog file.")

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
        print("'Chardet' library is unavailable. Install it or manually"
          "specify source encoding.")
        return -3

      detected_encoding = chardet.detect(binary_data)["encoding"]
      if not encoding_supported(detected_encoding):
        print("Detected encoding '{}' is not supported."
          .format(detected_encoding))
        return -4
      # Detected source encoding is supported by 'codecs'.
      source_encoding = detected_encoding

  with open(args.source, "r", encoding=source_encoding) as source:
    assembler = Assembler()
    # Check if 'target' parameter is specified.
    if args.target is not None:
      with open(args.target, "w", encoding="utf_8") as file_stream:
        assembler.assemble(source, file_stream)
    else:
      assembler.assemble(source, sys.stdout)

  return 0

# Allow running NanoAssembler as a script but not when it is imported
# as a module.
if __name__ == "__main__":
  # Return exit code from 'main' function.
  sys.exit(main())
