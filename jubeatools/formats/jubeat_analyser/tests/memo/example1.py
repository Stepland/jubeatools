from fractions import Fraction

from jubeatools.song import LongNote, NotePosition, TapNote

notes = {
    TapNote(time=Fraction(0, 1), position=NotePosition(x=0, y=0)),
    TapNote(time=Fraction(0, 1), position=NotePosition(x=0, y=1)),
    TapNote(time=Fraction(0, 1), position=NotePosition(x=0, y=3)),
    LongNote(
        time=Fraction(0, 1),
        position=NotePosition(x=1, y=0),
        duration=Fraction(1, 16),
        tail_tip=NotePosition(x=2, y=0),
    ),
    TapNote(time=Fraction(0, 1), position=NotePosition(x=1, y=1)),
    LongNote(
        time=Fraction(0, 1),
        position=NotePosition(x=1, y=2),
        duration=Fraction(1, 3),
        tail_tip=NotePosition(x=2, y=2),
    ),
    LongNote(
        time=Fraction(1, 8),
        position=NotePosition(x=0, y=3),
        duration=Fraction(1, 4),
        tail_tip=NotePosition(x=2, y=3),
    ),
    TapNote(time=Fraction(1, 4), position=NotePosition(x=0, y=0)),
    TapNote(time=Fraction(5, 16), position=NotePosition(x=1, y=0)),
    LongNote(
        time=Fraction(1, 2),
        position=NotePosition(x=0, y=0),
        duration=Fraction(1, 16),
        tail_tip=NotePosition(x=1, y=0),
    ),
    LongNote(
        time=Fraction(5, 8),
        position=NotePosition(x=0, y=3),
        duration=Fraction(1, 4),
        tail_tip=NotePosition(x=1, y=3),
    ),
    TapNote(time=Fraction(13, 16), position=NotePosition(x=0, y=0)),
    LongNote(
        time=Fraction(17, 16),
        position=NotePosition(x=0, y=0),
        duration=Fraction(1, 4),
        tail_tip=NotePosition(x=1, y=0),
    ),
    LongNote(
        time=Fraction(25, 16),
        position=NotePosition(x=0, y=0),
        duration=Fraction(1, 4),
        tail_tip=NotePosition(x=2, y=0),
    ),
    TapNote(time=Fraction(33, 16), position=NotePosition(x=0, y=0)),
    TapNote(time=Fraction(57, 8), position=NotePosition(x=1, y=1)),
    TapNote(time=Fraction(59, 8), position=NotePosition(x=1, y=1)),
    TapNote(time=Fraction(61, 8), position=NotePosition(x=1, y=1)),
    TapNote(time=Fraction(63, 8), position=NotePosition(x=1, y=1)),
    TapNote(time=Fraction(79, 8), position=NotePosition(x=1, y=1)),
    TapNote(time=Fraction(187, 16), position=NotePosition(x=1, y=0)),
    TapNote(time=Fraction(191, 16), position=NotePosition(x=1, y=0)),
    LongNote(
        time=Fraction(97, 8),
        position=NotePosition(x=1, y=1),
        duration=Fraction(1, 4),
        tail_tip=NotePosition(x=2, y=1),
    ),
    TapNote(time=Fraction(195, 16), position=NotePosition(x=1, y=0)),
}
