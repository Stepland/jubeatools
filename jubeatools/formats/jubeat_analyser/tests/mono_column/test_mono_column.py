from typing import Iterable, Union

import pytest

from jubeatools.formats.jubeat_analyser.mono_column.load import MonoColumnParser
from jubeatools.song import BeatsTime, LongNote, NotePosition, TapNote


def compare_chart_notes(
    chart: str, expected: Iterable[Union[TapNote, LongNote]]
) -> None:
    parser = MonoColumnParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    actual = list(parser.notes())
    assert set(expected) == set(actual)


def test_simple_section() -> None:
    chart = """
        ①□□□
        □⑤□□
        □□⑨□
        □□□⑬
        -------
        """
    expected = [
        TapNote(time=BeatsTime(i), position=NotePosition(i, i)) for i in range(4)
    ]
    compare_chart_notes(chart, expected)


def test_compound_section() -> None:
    chart = """
        □①①□
        □⑩⑪□
        ④⑧⑨⑤
        ③⑥⑦③

        ⑯⑫⑬⑯
        □□□□
        □□□□
        ⑭□□⑭
        ------------- 2
        """
    expected = [
        TapNote(time=BeatsTime("1/4") * (t - 1), position=NotePosition(x, y))
        for t, x, y in [
            (1, 1, 0),
            (1, 2, 0),
            (3, 0, 3),
            (3, 3, 3),
            (4, 0, 2),
            (5, 3, 2),
            (6, 1, 3),
            (7, 2, 3),
            (8, 1, 2),
            (9, 2, 2),
            (10, 1, 1),
            (11, 2, 1),
            (12, 1, 0),
            (13, 2, 0),
            (14, 0, 3),
            (14, 3, 3),
            (16, 0, 0),
            (16, 3, 0),
        ]
    ]
    compare_chart_notes(chart, expected)


def test_symbol_definition() -> None:
    chart = """
        *Ａ:2 //⑨と同タイミング
        *Ｂ:2.125
        *Ｃ:2.25 //⑩と同じ
        *Ｄ:2.375
        *Ｅ:2.5 //⑪と同じ
        *Ｆ:2.625
        *Ｇ:2.75 //⑫と同じ
        *Ｈ:2.875
        *Ｉ:3 //⑬と同じ
        *Ｊ:3.125
        *Ｋ:3.25 //⑭と同じ
        *Ｌ:3.375

        ＡＢＣＤ
        Ｌ③□Ｅ
        Ｋ⑦□Ｆ
        ＪＩＨＧ
        --
        """
    expected = [
        TapNote(BeatsTime(t), NotePosition(x, y))
        for t, x, y in [
            ("4/8", 1, 1),
            ("12/8", 1, 2),
            ("16/8", 0, 0),
            ("17/8", 1, 0),
            ("18/8", 2, 0),
            ("19/8", 3, 0),
            ("20/8", 3, 1),
            ("21/8", 3, 2),
            ("22/8", 3, 3),
            ("23/8", 2, 3),
            ("24/8", 1, 3),
            ("25/8", 0, 3),
            ("26/8", 0, 2),
            ("27/8", 0, 1),
        ]
    ]
    compare_chart_notes(chart, expected)


def test_half_width_symbols() -> None:
    chart = """
        b=7
        *⑲:4.5
        *21:5
        *25:6

        口⑪①口
        ①⑮⑤⑪
        ⑤口口⑮
        ⑨口口⑨

        21口口⑲
        25口口25
        口⑲21口
        25口口25
        ----------
        """
    expected = [
        TapNote(BeatsTime(t), NotePosition(x, y))
        for t, x, y in [
            ("0.0", 2, 0),
            ("0.0", 0, 1),
            ("1.0", 2, 1),
            ("1.0", 0, 2),
            ("2.0", 0, 3),
            ("2.0", 3, 3),
            ("2.5", 1, 0),
            ("2.5", 3, 1),
            ("3.5", 1, 1),
            ("3.5", 3, 2),
            ("4.5", 1, 2),
            ("4.5", 3, 0),
            ("5.0", 0, 0),
            ("5.0", 2, 2),
            ("6.0", 0, 1),
            ("6.0", 3, 1),
            ("6.0", 0, 3),
            ("6.0", 3, 3),
        ]
    ]
    compare_chart_notes(chart, expected)


def test_irregular_beats_per_frame_1() -> None:
    chart = """
        b=2.75
        ①□□□
        □□□□
        □□□□
        □□□□
        --
        □□□□
        □①□□
        □□□□
        □□□□
        --
        □□□□
        □□□□
        □□①□
        □□□□
        --
        □□□□
        □□□□
        □□□□
        □□□①
        --
        """
    expected = [
        TapNote(BeatsTime("0.00"), NotePosition(0, 0)),
        TapNote(BeatsTime("2.75"), NotePosition(1, 1)),
        TapNote(BeatsTime("5.50"), NotePosition(2, 2)),
        TapNote(BeatsTime("8.25"), NotePosition(3, 3)),
    ]
    compare_chart_notes(chart, expected)


def test_irregular_beats_per_frame_2() -> None:
    chart = """
        b=1
        ①□□□
        □□□□
        □□□□
        □□□□
        --
        □□□□
        □①□□
        □□□□
        □□□□
        --
        b=2.75
        □□□□
        □□□□
        □□①□
        □□□□
        --
        □□□□
        □□□□
        □□□□
        □□□①
        --
        """
    expected = [
        TapNote(BeatsTime("0.00"), NotePosition(0, 0)),
        TapNote(BeatsTime("1.00"), NotePosition(1, 1)),
        TapNote(BeatsTime("2.00"), NotePosition(2, 2)),
        TapNote(BeatsTime("4.75"), NotePosition(3, 3)),
    ]
    compare_chart_notes(chart, expected)


def test_long_notes() -> None:
    chart = """
        #holdbyarrow=1
        ①□□＜
        □□□□
        □□□□
        □□□□
        --
        ①□□□
        □□□□
        □□□□
        □□□□
        --
        """
    expected = [
        LongNote(
            time=BeatsTime(0),
            position=NotePosition(0, 0),
            duration=BeatsTime(4),
            tail_tip=NotePosition(3, 0),
        )
    ]
    compare_chart_notes(chart, expected)


def test_long_notes_ambiguous_case() -> None:
    chart = """
        #holdbyarrow=1
        ①①＜＜
        □□□□
        □□□□
        □□□□
        --
        ①①□□
        □□□□
        □□□□
        □□□□
        --
        """
    expected = [
        LongNote(BeatsTime(0), NotePosition(x, y), BeatsTime(4), NotePosition(tx, ty))
        for (x, y), (tx, ty) in [
            ((0, 0), (2, 0)),
            ((1, 0), (3, 0)),
        ]
    ]
    with pytest.warns(UserWarning):
        compare_chart_notes(chart, expected)


@pytest.mark.filterwarnings("error")
def test_long_notes_simple_solution_no_warning() -> None:
    chart = """
        #holdbyarrow=1
        □□□□
        ＞①①＜
        □□□□
        □□□□
        --
        □□□□
        □①①□
        □□□□
        □□□□
        --
        """
    expected = [
        LongNote(BeatsTime(0), NotePosition(x, y), BeatsTime(4), NotePosition(tx, ty))
        for (x, y), (tx, ty) in [
            ((1, 1), (0, 1)),
            ((2, 1), (3, 1)),
        ]
    ]
    compare_chart_notes(chart, expected)


def test_long_notes_complex_case() -> None:
    chart = """
        #holdbyarrow=1
        □□□□
        □□∨□
        □∨□□
        ＞①①①
        --
        □□□□
        □□□□
        □□□□
        □①①①
        --
        """
    expected = [
        LongNote(BeatsTime(0), NotePosition(x, y), BeatsTime(4), NotePosition(tx, ty))
        for (x, y), (tx, ty) in [
            ((1, 3), (1, 2)),
            ((2, 3), (2, 1)),
            ((3, 3), (0, 3)),
        ]
    ]
    compare_chart_notes(chart, expected)


def test_circle_free() -> None:
    chart = """
        #holdbyarrow=1
        #circlefree=1
        □□□□
        □□□□
        □□□□
        ＞□□①
        --
        □□□□
        □□□□
        □□□□
        □□□13
        --
        """
    expected = [
        LongNote(BeatsTime(0), NotePosition(3, 3), BeatsTime(7), NotePosition(0, 3))
    ]
    compare_chart_notes(chart, expected)
