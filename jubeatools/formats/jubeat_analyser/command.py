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

from decimal import ROUND_HALF_DOWN, Decimal
from fractions import Fraction
from functools import singledispatch
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from parsimonious import Grammar, NodeVisitor, ParseError
from parsimonious.nodes import Node

from jubeatools.utils import fraction_to_decimal

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
    quoted_value    = ~r"([^\"\\]|\\\"|\\\\)*"
    number          = ~r"-?\d+(\.\d+)?"
    ws              = ~r"[\t \u3000]*"
    comment         = ~r"//.*"
    """
)


class CommandVisitor(NodeVisitor):

    """Returns a (key, value) tuple"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.key: Optional[str] = None
        self.value: Optional[str] = None

    def visit_line(
        self, node: Node, visited_children: List[Node]
    ) -> Tuple[str, Optional[str]]:
        if self.key is None:
            raise ValueError("No key found after parsing command")
        return self.key, self.value

    def visit_hash_command(self, node: Node, visited_children: List[Node]) -> None:
        _, key, _ = node.children
        self.key = key.text

    def visit_short_command(self, node: Node, visited_children: List[Node]) -> None:
        letter, _ = node.children
        self.key = letter.text

    def visit_quoted_value(self, node: Node, visited_children: List[Node]) -> None:
        self.value = unescape_string_value(node.text)

    def visit_number(self, node: Node, visited_children: List[Node]) -> None:
        self.value = node.text

    def generic_visit(self, node: Node, visited_children: List[Node]) -> None:
        ...


def is_command(line: str) -> bool:
    try:
        command_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_command(line: str) -> Tuple[str, Optional[str]]:
    try:
        return CommandVisitor().visit(command_grammar.parse(line))  # type: ignore
    except ParseError:
        if line.strip()[0] == "#":
            raise ParseError(
                "Line starts with '#' but it couldn't be parsed as a valid command"
            ) from None
        else:
            raise


CommandValue = Union[str, Path, int, Decimal, Fraction]


def dump_command(key: str, value: Optional[CommandValue] = None) -> str:
    if len(key) == 1:
        key_part = key
    else:
        key_part = f"#{key}"

    if value is None:
        value_part = ""
    else:
        dumped_value = dump_value(value)
        value_part = f"={dumped_value}"

    return key_part + value_part


@singledispatch
def dump_value(value: CommandValue) -> str:
    return str(value)


@dump_value.register
def dump_int_value(value: int) -> str:
    return str(value)


@dump_value.register
def dump_decimal_value(value: Decimal) -> str:
    return pretty_print_decimal(value)


@dump_value.register
def dump_fraction_value(value: Fraction) -> str:
    decimal = fraction_to_decimal(value)
    quantized = decimal.quantize(Decimal("0.000001"), rounding=ROUND_HALF_DOWN)
    return pretty_print_decimal(quantized)


@dump_value.register
def dump_string_value(value: str) -> str:
    """Escapes backslashes and " from a string"""
    escaped = escape_string_value(value)
    quoted = f'"{escaped}"'
    return quoted


@dump_value.register
def dump_path_value(value: Path) -> str:
    if value == Path(""):
        string_value = ""
    else:
        string_value = str(value)

    escaped = escape_string_value(string_value)
    quoted = f'"{escaped}"'
    return quoted


def pretty_print_decimal(d: Decimal) -> str:
    raw_string_form = str(d)
    if "." in raw_string_form:
        return raw_string_form.rstrip("0").rstrip(".")
    else:
        return raw_string_form


BACKSLASH = "\\"
ESCAPE_TABLE = str.maketrans({'"': BACKSLASH + '"', BACKSLASH: BACKSLASH + BACKSLASH})


def escape_string_value(unescaped: str) -> str:
    return unescaped.translate(ESCAPE_TABLE)


def unescape_string_value(escaped: str) -> str:
    """Unescapes a backslash-escaped string"""
    res = []
    i = 0
    while i < len(escaped):
        char = escaped[i]
        if char == BACKSLASH:
            if i + 1 == len(escaped):
                raise ValueError("backslash at end of string")
            else:
                i += 1

        res.append(escaped[i])
        i += 1

    return "".join(res)
