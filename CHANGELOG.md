# v0.1.3
## Fixed
- memon : Fix TypeError that would occur when trying to convert to memon

# v0.1.2
## Fixed
- jubeat analyser
    - Fix decimal -> fraction conversion to correctly handle numbers with only 3 decimal places #1
    - Remove Vs from the allowed extra symbols lists as it would clash with long note arrows

# v0.1.1
## Fixed
- Loading a #memo2 file that did not specify any offset (neither by `o=...`, `r=...` nor `[...]` commands) would trigger a TypeError, not anymore ! Offset now defaults to zero.

# v0.1.0
- Initial Release