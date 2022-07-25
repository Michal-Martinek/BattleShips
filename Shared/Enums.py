from enum import IntEnum, auto

class STAGES(IntEnum):
    PAIRING = auto()
    PLACING = auto()
    SHOOTING = auto()
    END = auto()

class SHOTS(IntEnum):
    NOT_SHOTTED = auto()
    HITTED = auto()
    NOT_HITTED = auto()
    BLOCKED = auto()
    SHOTTED_UNKNOWN = auto()
