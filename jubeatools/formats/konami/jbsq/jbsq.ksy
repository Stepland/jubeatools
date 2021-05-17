meta:
  id: jbsq
  endian: le
  bit-endian: le
seq:
  - id: magic
    type: u4be
    enum: magic_bytes
  - id: num_events
    type: u4
  - id: combo
    type: u4
  - id: end_time
    type: u4
  - id: reserved1
    size: 2
  - id: starting_buttons
    type: u2
  - id: first_sector
    type: u4
  - id: reserved2
    size: 12
  - id: density_graph
    type: b4
    repeat: expr
    repeat-expr: 120
  - id: events
    type: event
    repeat: expr
    repeat-expr: num_events
enums:
  magic_bytes:
    0x494a4251: ijbq
    0x494a5351: ijsq
    0x4a425351: jbsq
  command:
    1: play
    2: end
    3: measure
    4: haku
    5: tempo
    6: long
  direction:
    0: down
    1: up
    2: right
    3: left
types:
  event:
    seq:
      - id: type
        type: b8
        enum: command
      - id: time_in_ticks
        type: b24
      - id: value
        type:
          switch-on: type
          cases:
            'command::play': play_value
            'command::end': zero_value
            'command::measure': zero_value
            'command::haku': zero_value
            'command::tempo': tempo_value
            'command::long': long_value
    instances:
      time_in_seconds:
        value: time_in_ticks / 300.0
  zero_value:
    seq:
      - id: value
        contents: [0, 0, 0, 0]
  play_value:
    seq:
      - id: note_position
        type: position
      - id: reserved
        type: b28
  tempo_value:
    seq:
      - id: tempo
        type: u4
    instances:
      bpm:
        value: 60000000.0 / tempo
  long_value:
    seq:
      - id: note_position
        type: position
      - id: tail_direction
        type: b2
        enum: direction
      - id: tail_length
        type: b2
      - id: duration_in_ticks
        type: b24
    instances:
      duration_in_seconds:
        value: duration_in_ticks / 300.0
  position:
    seq:
      - id: x
        type: b2
      - id: y
        type: b2