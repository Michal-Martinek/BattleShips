from pygame import Rect

GRID_HEIGHT = 10
GRID_WIDTH = 10

GRID_X_SPACING = 72
GRID_Y_SPACING = 72

SCREEN_WIDTH = GRID_HEIGHT * GRID_X_SPACING

HEADER_HEIGHT = 32
HEADER_ICON_CTR = (20, HEADER_HEIGHT // 2)
HEADER_NAME_POS = (32 + 10, HEADER_HEIGHT // 2)
HEADER_MINIMIZE_RECT = Rect(SCREEN_WIDTH - 64, 1, 32, HEADER_HEIGHT-1)
HEADER_MINIMIZE_LINE = [(HEADER_MINIMIZE_RECT.x + 16, HEADER_MINIMIZE_RECT.bottom - 12), (HEADER_MINIMIZE_RECT.right - 8, HEADER_MINIMIZE_RECT.bottom - 12)]
HEADER_CLOSE_RECT = Rect(SCREEN_WIDTH - 32, 0, 32, HEADER_HEIGHT)

HUD_RECT = Rect(0, HEADER_HEIGHT, SCREEN_WIDTH, 40)
HUD_BOUNDARY_RAD = 15
HUD_PLAYERNAME_OFFSETS = (17, 4), (SCREEN_WIDTH - 17, 4)
HUD_ICON_RECTS_DEFAULTS = Rect(12, 6, 0, 0), Rect(-12, 6, 0, 0)
HUD_READY_BTN_DEFAULTS = (12, HUD_RECT.bottom - HEADER_HEIGHT - 6)
HUD_SHIPBOX_RECTS = [Rect(HUD_RECT.centerx + 34 * i, 3, 32, 32) for i in range(-1, 3)]

THUMBNAIL_SPACINGS = 30
THUMBNAIL_CENTER_OFFSET = (SCREEN_WIDTH - THUMBNAIL_SPACINGS * 20) // 6
THUMBNAIL_GRID_RECTS = Rect(0, 400, THUMBNAIL_SPACINGS * GRID_WIDTH, THUMBNAIL_SPACINGS * GRID_HEIGHT)
THUMBNAIL_GRID_RECTS = [THUMBNAIL_GRID_RECTS.move(SCREEN_WIDTH // 2 - THUMBNAIL_CENTER_OFFSET - THUMBNAIL_GRID_RECTS.w, 0), THUMBNAIL_GRID_RECTS.move(SCREEN_WIDTH // 2 + THUMBNAIL_CENTER_OFFSET, 0)]
THUMBNAIL_MARGIN = 10
THUMBNAIL_OUTER_RECTS = [r.inflate(2*THUMBNAIL_MARGIN, 30+THUMBNAIL_MARGIN+4) for r in THUMBNAIL_GRID_RECTS]
for i, r in enumerate(THUMBNAIL_OUTER_RECTS):
	r.midbottom = THUMBNAIL_GRID_RECTS[i].midbottom
	r.move_ip(0, THUMBNAIL_MARGIN)

GRID_Y_OFFSET = HUD_RECT.bottom + 8
MULTIPLAYER_INPUT_BOX = Rect(150, 320, 300, 60)

SCREEN_HEIGHT = GRID_Y_OFFSET + GRID_Y_SPACING * GRID_HEIGHT + 8

FPS = 100
ANIMATION_TIMING = 400
