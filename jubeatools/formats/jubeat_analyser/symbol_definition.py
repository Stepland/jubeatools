"""
Note symbol definition
"""
from decimal import Decimal
from typing import List, Optional, Tuple

from parsimonious import Grammar, NodeVisitor, ParseError
from parsimonious.nodes import Node

beat_symbol_line_grammar = Grammar(
    r"""
    line    = "*" symbol ":" number comment?
    symbol  = ws ~r"[^*#:|\-/\s]{1,2}" ws
    number  = ws ~r"\d+(\.\d+)?" ws
    ws      = ~r"[\t \u3000]*"
    comment = ~r"//.*"
    """
)


class BeatSymbolVisitor(NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.symbol: Optional[str] = None
        self.number: Optional[Decimal] = None

    def visit_line(
        self, node: Node, visited_children: List[Node]
    ) -> Tuple[str, Decimal]:
        if self.symbol is None:
            raise ValueError("No symbol found after parsing symbol definition")
        if self.number is None:
            raise ValueError("No value found after parsing symbol definition")
        return self.symbol, self.number

    def visit_symbol(self, node: Node, visited_children: List[Node]) -> None:
        _, symbol, _ = node.children
        self.symbol = symbol.text

    def visit_number(self, node: Node, visited_children: List[Node]) -> None:
        _, number, _ = node.children
        self.number = Decimal(number.text)

    def generic_visit(self, node: Node, visited_children: List[Node]) -> None:
        ...


def is_symbol_definition(line: str) -> bool:
    try:
        beat_symbol_line_grammar.parse(line)
    except ParseError:
        return False
    else:
        return True


def parse_symbol_definition(line: str) -> Tuple[str, Decimal]:
    return BeatSymbolVisitor().visit(beat_symbol_line_grammar.parse(line))  # type: ignore
