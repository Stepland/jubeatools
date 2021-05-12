# 1.0.1
## Fixed
- Remove debug `print(locals())` mistakenly left in

# 1.0.0
## Added
- [eve]
    - 🎉 .eve support !
    - Add `--beat-snap={number}` loader option to allow aggressive rounding
- Loaders can now take in arguments
## Fixed
- Fix infinite loop that would occur when choosing a deduplicated filename
- [jubeat-analyser] Prettier rendering of decimal values

# v0.2.0
## Added
- [mono-column] #circlefree mode accepts non-16ths notes and falls back to normal symbols when needed
## Fixed
- [jubeat-analyser]
    - Raise exception earlier when a mono-column file is detected by the other #memo parsers (based on "--" separator lines)
    - [memo] [memo1]
        - Fix incorrect handling of mid-chart `t=` and `b=` commands
        - Prettify rendering by adding more blank lines between sections
    - [memo1] Fix dumping of chart with bpm changes happening on beat times that aren't multiples of 1/4
    - [memo2]
        - Fix parsing of BPM changes
        - Fix dumping of BPM changes
- [memon]
    - Fix handling of paths-type values in metadata
    - Fix handling of charts with decimal level value

# v0.1.3
## Changed
- [jubeat-analyser] Use "EXT" instead of "?" as the fallback difficulty name when loading
## Fixed
- [memon] Fix TypeError that would occur when trying to convert
- [memo2] Fix rendering missing blank lines between blocks, while technically still valid files, this made files rendered by jubeatools absolutely fugly and very NOT human friendly

# v0.1.2
## Fixed
- [jubeat-analyser]
    - Fix decimal -> fraction conversion to correctly handle numbers with only 3 decimal places #1
    - Remove Vs from the allowed extra symbols lists as it would clash with long note arrows

# v0.1.1
## Fixed
- [memo2] Loading a file that did not specify any offset (neither by `o=...`, `r=...` nor `[...]` commands) would trigger a TypeError, not anymore ! Offset now defaults to zero.

# v0.1.0
- Initial Release