"""
memo is a vague term refering to several legacy formats.
They were originally derived from the (somewhat) human-readable format choosen
by websites storing official jubeat charts in text form as a memory aid.

The machine-readable variants are partially documented (in japanese)
on these pages :
- http://yosh52.web.fc2.com/jubeat/fumenformat.html
- http://yosh52.web.fc2.com/jubeat/holdmarker.html

Known simple commands :
  - b=<decimal>   : beats per measure (4 by default)
  - m="<path>"    : music file path
  - o=<int>       : offset in ms (100 by default)
  - r=<int>       : increase the offset (in ms)
  - t=<decimal>   : tempo
  
Known hash commands :
  - #memo             # mono-column format
  - #memo1            # youbeat-like but missing a lot of the youbeat features
  - #memo2            # youbeat-like memo
  - #boogie           # youbeat
  - #pw=<int>         # number of panels horizontally (4 by default)
  - #ph=<int>         # number of panels vertically (4 by default)
  - #lev=<int>        # chart level (typically 1 to 10)
  - #dif={1, 2, 3}    # 1: BSC, 2: ADV, 3: EXT
  - #title="<str>"    # music title
  - #artist="<str>"   # artist's name
  - #jacket="<path>"  # music cover art path
  - #prevpos=<int>    # preview start (in ms)
  - #bpp              # bytes per panel (2 by default)
"""
