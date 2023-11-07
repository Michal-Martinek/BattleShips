from enum import Enum, IntEnum, auto

class STAGES(IntEnum):
	MAIN_MENU = auto()
	CONNECTING = auto()
	PAIRING = auto()
	PLACING = auto()
	GAME_WAIT = auto()
	SHOOTING = auto()
	GETTING_SHOT = auto()
	WON = auto()
	LOST = auto()
	CLOSING = auto()

	COUNT = auto()

class SHOTS(IntEnum):
	NOT_SHOTTED = auto()
	HITTED = auto()
	HITTED_WHOLE = auto()
	NOT_HITTED = auto()
	BLOCKED = auto()
	SHOTTED_UNKNOWN = auto()

class COM(str, Enum):
	CONNECT = '!CONNECT'
	CONNECTION_CHECK = '!CONNECTION_CHECK'
	PAIR = '!PAIR'
	GAME_READINESS = '!GAME_READINESS'
	GAME_WAIT = '!GAME_WAIT'
	SHOOT = '!SHOOT'
	OPPONENT_SHOT = '!OPPONENT_SHOT'

	DISCONNECT = '!DISCONNECT'
	ERROR = '!ERROR'
