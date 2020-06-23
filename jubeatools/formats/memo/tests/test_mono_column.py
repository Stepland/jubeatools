from typing import Union, Iterable

from jubeatools.formats.memo.mono_column import MonoColumnParser
from jubeatools.song import TapNote, BeatsTime, NotePosition, LongNote


def compare_chart_notes(chart: str, expected: Iterable[Union[TapNote, LongNote]]):
    parser = MonoColumnParser()
    for line in chart.split("\n"):
        parser.load_line(line)
    actual = list(parser.notes())
    assert set(expected) == set(actual)


def test_simple_mono_column():
    chart = (
        """
        ①□□□
        □⑤□□
        □□⑨□
        □□□⑬
        -------
        """
    )
    expected = [
        TapNote(time=BeatsTime(i), position=NotePosition(i,i))
        for i in range(4)
    ]
    compare_chart_notes(chart, expected)

def test_compound_section_mono_column():
    chart = (
        """
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
    )
    expected = [
        TapNote(time=BeatsTime("0.25")*(t-1), position=NotePosition(x,y))
        for t,x,y in [
            ( 1, 1, 0),
            ( 1, 2, 0),
            ( 3, 0, 3),
            ( 3, 3, 3),
            ( 4, 0, 2),
            ( 5, 3, 2),
            ( 6, 1, 3),
            ( 7, 2, 3),
            ( 8, 1, 2),
            ( 9, 2, 2),
            (10, 1, 1),
            (11, 2, 1),
            (12, 1, 0),
            (13, 2, 0),
            (14, 0, 3),
            (14, 3, 3),
            (16, 0, 0),
            (16, 3, 0)
        ]
    ]
    compare_chart_notes(chart, expected)
