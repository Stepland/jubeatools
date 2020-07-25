"""
Useful things to parse and dump the jubeat analyser command format

Known simple commands :
  - b=<decimal>   : beats per measure (4 by default)
  - m="<path>"    : music file path
  - o=<int>       : offset in ms (100 by default)
  - r=<int>       : ? increase the offset ? (in ms) (not supported, couldn't find any examples, wtf is it for ?)
  - t=<decimal>   : tempo
  
Known hash commands :
  - #memo             # youbeat-like format but a bar division always means a 1/4 note (amongst other quirks)
  - #memo1            # youbeat-like but without bpm changes in the bar
  - #memo2            # youbeat-like but double-width
  - #boogie           # youbeat-like
  - #pw=<int>         # number of panels horizontally (4 by default)
  - #ph=<int>         # number of panels vertically (4 by default)
  - #lev=<int>        # chart level (typically 1 to 10)
  - #dif={1, 2, 3}    # 1: BSC, 2: ADV, 3: EXT
  - #title="<str>"    # music title
  - #artist="<str>"   # artist's name
  - #jacket="<path>"  # music cover art path
  - #prevpos=<int>    # preview start (in ms)
  - #bpp              # bytes per panel (2 by default)
"""

from decimal import Decimal
from numbers import Number
from typing import Any, Iterable, List, Optional, Tuple, Union

from parsimonious import Grammar, NodeVisitor, ParseError

command_grammar = Grammar(
    r"""
    line            = ws command ws comment?
    command         = hash_command / short_command
    hash_command    = "#" key equals_value?
    short_command   = letter equals_value
    letter          = ~r"\w"
    key             = ~r"\w+"
    equals_value    = ws "=" ws value
    value           = value_in_quotes / number
    value_in_quotes = '"' quoted_value '"'
    quoted_value    = ~r"[^\"]*"
    number          = ~r"-?\d+(\.\d+)?"
    ws              = ~r"[\t ]*"
    comment         = ~r"//.*"
    """
)


class CommandVisitor(NodeVisitor):

    """Returns a (key, value) tuple or None if the line contains no useful
    information for the parser (a comment or an empty line)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = None
        self.value = None

    def visit_line(self, node, visited_children):
        return self.key, self.value

    def visit_hash_command(self, node, visited_children):
        _, key, _ = node.children
        self.key = key.text

    def visit_short_command(self, node, visited_children):
        letter, _ = node.children
        self.key = letter.text

    def visit_quoted_value(self, node, visited_children):
        self.value = node.text

    def visit_number(self, node, visited_children):
        self.value = node.text

    def generic_visit(self, node, visited_children):
        ...


def is_command(line: str) -> bool:
    try:
        command_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_command(line: str) -> Tuple[str, str]:
    try:
        return CommandVisitor().visit(command_grammar.parse(line))
    except ParseError:
        if line.strip()[0] == "#":
            raise ParseError(f"Invalid command syntax : {line}") from None
        else:
            raise


def dump_command(key: str, value: Any = None) -> str:
    if len(key) == 1:
        key_part = key
    else:
        key_part = f"#{key}"

    if isinstance(value, Number):
        value_part = f"={value}"
    elif value is not None:
        value_part = f'="{value}"'
    else:
        value_part = ""

    return key_part + value_part
