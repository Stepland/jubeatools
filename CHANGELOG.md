# v0.1.1
## Fixed
- Loading a #memo2 file that did not specify any offset (neither by `o=...`, `r=...` nor `[...]` commands) would trigger a TypeError, not anymore ! Offset now defaults to zero.


# v0.1.0
- Initial Release