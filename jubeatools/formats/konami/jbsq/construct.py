"""The JBSQ format described using construct.
see https://construct.readthedocs.io/en/latest/index.html"""

from dataclasses import dataclass
from typing import List, Optional

import construct as c
import construct_typed as ct


class EventType(ct.EnumBase):
    PLAY = 1
    END = 2
    MEASURE = 3
    HAKU = 4
    TEMPO = 5
    LONG = 6


@dataclass
class Event(ct.TContainerMixin):
    type_: EventType = ct.sfield(ct.TEnum(c.Byte, EventType))
    time_in_ticks: int = ct.sfield(c.Int24ul)
    value: int = ct.sfield(c.Int32ul)


@dataclass
class JBSQ(ct.TContainerMixin):
    magic: Optional[bytes] = ct.sfield(
        c.Select(c.Const(b"IJBQ"), c.Const(b"IJSQ"), c.Const(b"JBSQ"))
    )
    num_events: int = ct.sfield(c.Int32ul)
    combo: int = ct.sfield(c.Int32ul)
    end_time: int = ct.sfield(c.Int32ul)
    _1: None = ct.sfield(c.Padding(2))
    starting_buttons: int = ct.sfield(c.Int16ul)
    start_time: int = ct.sfield(c.Int32ul)
    _2: None = ct.sfield(c.Padding(12))
    density_graph: List[int] = ct.sfield(c.Byte[60])
    events: List[Event] = ct.sfield(c.Array(c.this.num_events, ct.TStruct(Event)))


jbsq = ct.TStruct(JBSQ)
