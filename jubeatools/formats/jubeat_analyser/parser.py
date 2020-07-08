"""Base class and tools for the different parsers"""
from copy import deepcopy
from .symbols import NOTE_SYMBOLS
from decimal import Decimal
from jubeatools.song import BPMEvent

DIFFICULTIES = {1: "BSC", 2: "ADV", 3: "EXT"}

SYMBOL_TO_DECIMAL_TIME = {
    symbol: Decimal("0.25") * index for index, symbol in enumerate(NOTE_SYMBOLS)
}


class JubeatAnalyserParser:
    def __init__(self):
        self.music = None
        self.symbols = deepcopy(SYMBOL_TO_DECIMAL_TIME)
        self.current_beat = Decimal("0")
        self.current_tempo = None
        self.current_chart_lines = []
        self.timing_events = []
        self.offset = 0
        self.beats_per_section = 4
        self.bytes_per_panel = 2
        self.level = 1
        self.difficulty = None
        self.title = None
        self.artist = None
        self.jacket = None
        self.preview_start = None
        self.hold_by_arrow = False
        self.circle_free = False

    def handle_command(self, command, value=None):
        try:
            method = getattr(self, f"do_{command}")
        except AttributeError:
            raise SyntaxError(f"Unknown analyser command : {command}") from None

        if value is not None:
            method(value)
        else:
            method()

    def do_m(self, value):
        self.music = value

    def do_t(self, value):
        self.current_tempo = Decimal(value)
        self.timing_events.append(BPMEvent(self.current_beat, BPM=self.current_tempo))

    def do_o(self, value):
        self.offset = int(value)

    def do_b(self, value):
        self.beats_per_section = Decimal(value)

    def do_pw(self, value):
        if int(value) != 4:
            raise ValueError("jubeatools only supports 4×4 charts")

    do_ph = do_pw

    def do_lev(self, value):
        self.level = int(value)

    def do_dif(self, value):
        dif = int(value)
        if dif <= 0:
            raise ValueError(f"Unknown chart difficulty : {dif}")
        if dif < 4:
            self.difficulty = DIFFICULTIES[dif]
        else:
            self.difficulty = f"EDIT-{dif-3}"

    def do_title(self, value):
        self.title = value

    def do_artist(self, value):
        self.artist = value

    def do_jacket(self, value):
        self.jacket = value

    def do_prevpos(self, value):
        self.preview_start = int(value)

    def do_bpp(self, value):
        bpp = int(value)
        if bpp not in (1, 2):
            raise ValueError(f"Unexcpected bpp value : {value}")
        elif self.circle_free and bpp == 1:
            raise ValueError("#bpp can only be 2 when #circlefree is activated")
        else:
            self.bytes_per_panel = int(value)

    def do_holdbyarrow(self, value):
        self.hold_by_arrow = int(value) == 1

    def do_holdbytilde(self, value):
        if int(value):
            raise ValueError("jubeatools does not support #holdbytilde")

    def do_circlefree(self, raw_value):
        activate = bool(int(raw_value))
        if activate and self.bytes_per_panel != 2:
            raise ValueError("#circlefree can only be activated when #bpp=2")
        self.circle_free = activate

    def define_symbol(self, symbol: str, timing: Decimal):
        bpp = self.bytes_per_panel
        length_as_shift_jis = len(symbol.encode("shift_jis_2004"))
        if length_as_shift_jis != bpp:
            raise ValueError(
                f"Invalid symbol definition. Since #bpp={bpp}, timing symbols "
                f"should be {bpp} bytes long but '{symbol}' is {length_as_shift_jis}"
            )
        if timing > self.beats_per_section:
            message = (
                "Invalid symbol definition conscidering the number of beats per section :\n"
                f"*{symbol}:{timing}"
            )
            raise ValueError(message)
        self.symbols[symbol] = timing