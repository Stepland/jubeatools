"""
Useful things to parse the header of analyser-like formats
"""
from decimal import Decimal
from typing import List, Tuple, Union, Iterable, Optional

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
    quoted_value    = ~r"[^\"]+"
    number          = ~r"\d+(\.\d+)?"
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