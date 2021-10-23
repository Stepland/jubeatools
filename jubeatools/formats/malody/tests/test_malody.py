from dataclasses import fields
from decimal import Decimal
from typing import Optional

import simplejson as json
from hypothesis import given
from hypothesis import strategies as st

from jubeatools import song
from jubeatools.formats import Format
from jubeatools.formats.malody import schema as malody
from jubeatools.formats.malody.dump import dump_malody_chart
from jubeatools.testutils import strategies as jbst
from jubeatools.testutils.test_patterns import dump_and_load_then_compare


@st.composite
def difficulty(draw: st.DrawFn) -> str:
    d: song.Difficulty = draw(st.sampled_from(list(song.Difficulty)))
    return d.value


@st.composite
def chart(draw: st.DrawFn) -> song.Chart:
    c: song.Chart = draw(jbst.chart(level_strat=st.just(Decimal(0))))
    return c


@st.composite
def metadata(draw: st.DrawFn) -> song.Metadata:
    metadata: song.Metadata = draw(jbst.metadata())
    metadata.preview = None
    metadata.preview_file = None
    return metadata


@st.composite
def malody_song(draw: st.DrawFn) -> song.Song:
    """Malody files only hold one chart and have limited metadata"""
    diff = draw(difficulty())
    chart_ = draw(chart())
    metadata_ = draw(metadata())
    return song.Song(metadata=metadata_, charts={diff: chart_})


@given(malody_song())
def test_that_full_chart_roundtrips(s: song.Song) -> None:
    dump_and_load_then_compare(
        Format.MALODY,
        s,
        bytes_decoder=lambda b: b.decode("utf-8"),
    )


@given(chart(), metadata(), st.one_of(st.none(), difficulty()))
def test_that_none_values_in_metadata_dont_appear_in_dumped_json(
    chart: song.Chart,
    metadata: song.Metadata,
    dif: Optional[str],
) -> None:
    assert chart.timing is not None
    malody_chart = dump_malody_chart(metadata, dif, chart, chart.timing)
    json_chart = malody.CHART_SCHEMA.dump(malody_chart)
    assert all(value is not None for value in json_chart["meta"].values())


@given(malody_song())
def test_that_field_are_ordered(s: song.Song) -> None:
    dif, chart = next(iter(s.charts.items()))
    assert chart.timing is not None
    malody_chart = dump_malody_chart(s.metadata, dif, chart, chart.timing)
    json_chart = malody.CHART_SCHEMA.dump(malody_chart)
    text_chart = json.dumps(json_chart, indent=4, use_decimal=True)
    reparsed_chart = json.loads(
        text_chart,
    )
    # dict is ordered in 3.8 ... right ?
    order_in_file = list(reparsed_chart["meta"].keys())
    order_in_definition = list(
        f.name for f in fields(malody.Metadata) if f.name in reparsed_chart["meta"]
    )
    assert order_in_file == order_in_definition
