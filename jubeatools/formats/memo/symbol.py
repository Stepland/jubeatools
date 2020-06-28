"""
Beat symbol definition
"""
from decimal import Decimal
from typing import Optional, Tuple

from parsimonious import Grammar, NodeVisitor, ParseError

beat_symbol_line_grammar = Grammar(
    r"""
    line    = "*" symbol ":" number comment?
    symbol  = ws ~r"[^*#:|\-/\s]{1,2}" ws
    number  = ws ~r"\d+(\.\d+)?" ws
    ws      = ~r"\s*"
    comment = ~r"//.*"
    """
)


class BeatSymbolVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.symbol = None
        self.number = None

    def visit_line(self, node, visited_children):
        return self.symbol, self.number

    def visit_symbol(self, node, visited_children):
        _, symbol, _ = node.children
        self.symbol = symbol.text

    def visit_number(self, node, visited_children):
        _, number, _ = node.children
        self.number = Decimal(number.text)

    def generic_visit(self, node, visited_children):
        ...


def is_symbol_definition(line: str) -> bool:
    try:
        beat_symbol_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_symbol_definition(line: str) -> Tuple[str, Decimal]:
    return BeatSymbolVisitor().visit(beat_symbol_line_grammar.parse(line))
