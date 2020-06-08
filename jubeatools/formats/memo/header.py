"""
Useful things to parse the header of analyser-like formats
"""
from decimal import Decimal
from typing import List, Tuple, Union, Iterable

from parsimonious import Grammar, NodeVisitor
from parsimonious.expressions import Node

header_line_grammar = Grammar(
    r"""
    raw_line        = line comment?
    line            = command? ws
    command         = hash_command / simple_command
    hash_command    = "#" key "=" value
    key             = ~"[a-z]+"
    value           = value_in_quotes / number
    value_in_quotes = "\"" quoted_value "\""
    quoted_value    = ~"[^\"]+"
    number          = ~"\d+"
    simple_command  = letter "=" value
    letter          = ~"\w"
    ws              = ~"[\t ]*"
    comment         = ~"//.*"
    """
)


class HeaderLineVisitor(NodeVisitor):

    """Returns a (key, value) tuple or None if the line contains no useful
    information for the parser (a comment or an empty line)"""

    def _as_text(self, node, visited_children):
        return node.text

    def visit_raw_line(self, node, visited_children):
        value, _ = visited_children
        return value

    def visit_line(self, node, visited_children):
        command, _ = visited_children
        value = list(command)
        return value[0] if value else None

    visit_command = NodeVisitor.lift_child

    def visit_hash_command(self, node, visited_children):
        _, key, _, value = visited_children
        return (key, value)

    visit_key = _as_text

    visit_value = NodeVisitor.lift_child

    def visit_value_in_quotes(self, node, visited_children):
        _, value, _ = visited_children
        return value

    visit_quoted_value = _as_text

    def visit_number(self, node, visited_children):
        return Decimal(node.text)

    def visit_simple_command(self, node, visited_children):
        letter, _, value = visited_children
        return (letter, value)

    visit_letter = _as_text

    def generic_visit(self, node, visited_children):
        return visited_children or node


_header_line_visitor = HeaderLineVisitor()


def load_preamble_line(line: str) -> Union[Tuple[str, Union[str, Decimal]], None]:
    _header_line_visitor.visit(header_line_grammar.parse(line))


def first_non_header_line(lines: Iterable[str]) -> int:
    """Return the index of the first line on the iterable which does not
    parse correctly as header line"""
    res = 0
    for line in lines:
        try:
            header_line_grammar.parse(line)
        except Exception:
            break
        else:
            res += 1
    return res