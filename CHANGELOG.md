# v1.3.0
## Added
- [memon] 🎉 v0.3.0 support

# v1.2.3
## Fixed
- Loaders and Dumpers would recieve options with unwanted default values when
  their corresponding flags were not passed to the commandline, resulting
  in weird bugs, not anymore ! #17

# v1.2.2
## Changed
- Slashes in filenames are now ignored
## Fixed
- Bug when using braces in output filenames
- [malody] Dumping does not write placeholder `null` values anymore

# v1.2.1
## Fixed
- [malody] Parsing a file with keys that are unused for conversion
  (like `meta.mode_ext` or `extra`) would fire errors, not anymore !

# v1.2.0
## Added
- [malody] 🎉 initial malody support !

# v1.1.3
## Fixed
- [jubeat-analyser] All files are read and written in `surrogateescape` error
  mode to mimick the way jubeat analyser handles files at the byte level, without
  caring about whether the whole file can be properly decoded as shift-jis or not
  (Thanks Nomlas and Mintice for noticing this !)

# v1.1.2
## Fixed
- [jubeat-analyser]
    - Accept U+3000 (Ideographic space) as valid whitespace
    - [memo2]
        - Accept `t=` commands anywhere in the file
        - Accept `b=4` (and only 4) anywhere in the file

# v1.1.1
## Fixed
- `construct-typing` is now required for all builds

# v1.1.0
## Added
- [jbsq] 🎉 initial .jbsq support !

# v1.0.1
## Fixed
- Remove debug `print(locals())` mistakenly left in

# v1.0.0
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