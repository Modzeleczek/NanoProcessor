from __future__ import annotations
import argparse
from io import TextIOWrapper
import os
import sys
from typing import TextIO
import codecs
from types import SimpleNamespace

class Assembler:
  def assemble(self, source: TextIOWrapper,
    target: TextIO | TextIOWrapper) -> None:
    source.seek(0, 0)
    for token in self.tokenize(source):
      if token == "\n":
        target.write("~")
      else:
        target.write(token)

  # This function is a coroutine (https://en.wikipedia.org/wiki/Coroutine)
  # because it is paused using 'yield' and resumed by being called again.
  def tokenize(self, source: TextIOWrapper) -> str:
    states = SimpleNamespace()
    states.WHITESPACE = 0
    states.NEWLINE = 1
    states.COMMENT = 2
    states.TEXT = 3

    state = states.WHITESPACE
    text_token = None
    last_newline_char = None
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
              return None
            # else last_newline_char == "\n" -
            # A newline token for "\n" has already been returned.
            # 'None' returned by the generator breaks a 'for in' loop.
            return None
          case states.TEXT:
            yield text_token
            return None
          case _: # default
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
