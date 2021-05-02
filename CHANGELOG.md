# Unreleased
## Fixed
- [jubeat-analyser] Raise exception earlier when a mono-column file is detected by the other #memo parsers (based on "--" separator lines)

# v0.1.3
## Changed
- [jubeat-analyser] Use "EXT" instead of "?" as the fallback difficulty name when loading
## Fixed
- [memon] Fix TypeError that would occur when trying to convert
- [#memo2] Fix rendering missing blank lines between blocks, while technically still valid files, this made files rendered by jubeatools absolutely fugly and very NOT human friendly

# v0.1.2
## Fixed
- [jubeat-analyser]
    - Fix decimal -> fraction conversion to correctly handle numbers with only 3 decimal places #1
    - Remove Vs from the allowed extra symbols lists as it would clash with long note arrows

# v0.1.1
## Fixed
- [#memo2] Loading a file that did not specify any offset (neither by `o=...`, `r=...` nor `[...]` commands) would trigger a TypeError, not anymore ! Offset now defaults to zero.

# v0.1.0
- Initial Release