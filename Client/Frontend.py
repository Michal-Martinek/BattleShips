import os
import logging, traceback
from dataclasses import dataclass
import pygame
from . import Constants
from Shared.Enums import STAGES
pygame.init()
from pygame._sdl2 import Window

# globals ------------------------------------------------------------
GRAPHICS_DIR = os.path.join('Client', 'Graphics')
assert os.path.exists(GRAPHICS_DIR), 'Graphics directory not found'
COLORKEY = (255, 174, 201)

IMG_ERR = pygame.Surface((30, 30))
IMG_ERR.fill((255, 0, 0))
pygame.draw.rect(IMG_ERR, (118, 205, 226), (5, 4, 25, 8))
pygame.draw.rect(IMG_ERR, (118, 205, 226), (5, 17, 25, 9))

FONT_ARIAL_MIDDLE = pygame.font.SysFont('arial', 40)
FONT_ARIAL_MSGS = pygame.font.SysFont('arial', 30)
FONT_ARIAL_BIG = pygame.font.SysFont('arial', 60)
FONT_ARIAL_PLAYERNAME = pygame.font.SysFont('arial', 22)
FONT_ARIAL_SMALL = pygame.font.SysFont('arial', 20)
FONT_ARIAL17 = pygame.font.SysFont('arial', 17)

def loadImage(*paths) -> pygame.Surface:
	path = os.path.join(GRAPHICS_DIR, *paths)
	try:
		img = pygame.image.load(path).convert()
	except FileNotFoundError:
		logging.error(f'The image {path} could not be found')
		img = IMG_ERR.copy()
	img.set_colorkey(COLORKEY)
	return img

# runtime ---------------------------------------------------------------
@dataclass
class _Runtime:
	'''holds Frontend related runtime variables'''
	display: pygame.Surface
	SDLwindow: Window
	windowGrabbedPos: list[int, int] = None
	headerMinimizeActive = False
	headerCloseActive = False
	windowHasFocus = True
	readyBtnHovered = False
	readyBtnRect: pygame.Rect = None # NOTE: Rect only if btn hoverable
	shipboxRects: dict[int, pygame.Rect] = None
	shipboxHovered: set[int] = None
	thumbnailHovers: list[bool] = None

	def __init__(self):
		self.display = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT), pygame.NOFRAME)
		self.SDLwindow = Window.from_display_module()
		self.SDLwindow.position = (self.SDLwindow.position[0], 6)
		pygame.display.set_caption('Battleships')
		pygame.display.set_icon(loadImage('BattleShips.ico'))
		self.resetVars()
	def resetVars(self):
		self.readyBtnHovered = False
		self.readyBtnRect = None
		self.shipboxRects = dict()
		self.shipboxHovered = set()
		self.thumbnailHovers = [False, False]

Runtime = _Runtime()

# ship frame generation --------------------------------------------------
SHIP_FRAMES: dict[str, pygame.Surface] = dict()
def _loadShipFragment(size, fragment, frame) -> pygame.Surface:
	return loadImage('Ships', f'{size}-ship', f'{fragment}_{frame+1}.png')
def _getFrameStrings(size, horizontal, hitted) -> tuple[list[str], tuple[int]]:
	hor = 'H' if horizontal else 'V'
	alives = [['A', 'D'][h] for h in hitted]
	sideIndicator = ['TB', 'LR'][horizontal]
	if size == 1: return [hor + alives[0]]
	if size == 2:
		if all(hitted): return [hor + 'D' + sideIndicator]
		return [hor + alives[0] + sideIndicator[0], hor + alives[1] + sideIndicator[1]], (0, 0, (not horizontal and hitted[1]) * 12)
	if size == 3:
		if all(hitted) and not horizontal: return ['VD_TMB']
		tops = sideIndicator[0] * hitted[0] + 'M' * hitted[1] * horizontal
		tops2 = '_' * bool(len(tops)) + tops
		downs = 'M' * hitted[1] + sideIndicator[1] * hitted[2]
		downs2 = '_' * bool(len(downs)) + downs
		return [hor + ('ADD'[len(tops)]) + sideIndicator[0] + tops2 * horizontal, hor + ('ADD'[len(downs)]) + sideIndicator[1] + downs2], (0, 6 * hitted[1] * hitted[2] * (not horizontal), (not horizontal) * hitted[1] * (9 + 3 * hitted[2]))
	if size == 4:
		if all(hitted): return [hor + 'DA'], 0
		tops = sideIndicator[0] * hitted[0] + sideIndicator[1] * hitted[1]
		tops2 = '_' * bool(len(tops)) + tops
		downs = sideIndicator[0] * hitted[2] + sideIndicator[1] * hitted[3]
		downs2 = '_' * bool(len(downs)) + downs
		return [hor + ('ADD'[len(tops)]) + sideIndicator[0] + tops2, hor + ('ADD'[len(downs)]) + sideIndicator[1] + downs2], (3 * (not horizontal) * hitted[0] * hitted[1], 6 * (not horizontal) * hitted[2] * hitted[3], 0)
def _mergeImgs(surf1, surf2, horizontal: bool, verticalOffsets) -> pygame.Surface:
	if horizontal:
		s = pygame.Surface((surf1.get_width() + surf2.get_width(), max(surf1.get_height(), surf2.get_height())))
		s.fill(COLORKEY)
		s.blit(surf1, (0, max(0, surf2.get_height() - surf1.get_height())))
		s.blit(surf2, (surf1.get_width(), max(0, surf1.get_height() - surf2.get_height())))
	else:
		s = pygame.Surface((max(surf1.get_width(), surf2.get_width()), surf1.get_height() + surf2.get_height() - verticalOffsets[2]))
		s.fill(COLORKEY)
		s.blit(surf1, (max(0, verticalOffsets[1] - verticalOffsets[0]), 0))
		s.blit(surf2, (max(0, verticalOffsets[0] - verticalOffsets[1]), surf1.get_height() - verticalOffsets[2]))
	s.set_colorkey(COLORKEY)
	return s
def _getFrameImpl(size, horizontal, hitted, frame) -> pygame.Surface:
	out = _getFrameStrings(size, horizontal, hitted)
	if isinstance(out, tuple):
		strs, offsets = out
	else:
		strs = out
		offsets = (0, 0, 0)
	if len(strs) == 1: return _loadShipFragment(size, strs[0], frame)
	assert len(strs) == 2, 'invalid strs'
	return _mergeImgs(*[_loadShipFragment(size, s, frame) for s in strs], horizontal, offsets)
def getFrame(size: int, horizontal: bool, hitted: list[bool], frame: int) -> pygame.Surface:
	frameStr = str(size) + '-' + str(int(horizontal)) + '-' + ''.join([str(int(x)) for x in hitted]) + '-' + str(frame)
	if frameStr in SHIP_FRAMES: return SHIP_FRAMES[frameStr]
	try:
		frame = _getFrameImpl(size, horizontal, hitted, frame)
	except Exception as e:
		logging.error(f'failed to generate animation frame for {frameStr}: ' + traceback.format_exception(type(e), e, None)[0][:-1])
		frame = IMG_ERR.copy()
	SHIP_FRAMES[frameStr] = frame
	return frame

# interface ------------------------------------------------------------
def grabWindow(mousePos):
	if mousePos[1] <= Constants.HEADER_HEIGHT:
		Runtime.windowGrabbedPos = list(mousePos)
		return True
def moveWindow(mousePos):
	Runtime.SDLwindow.position = Runtime.SDLwindow.position[0] - Runtime.windowGrabbedPos[0] + mousePos[0], Runtime.SDLwindow.position[1] - Runtime.windowGrabbedPos[1] + mousePos[1]
def headerBtnCollide(mousePos) -> bool:
	minColl, closeColl = Constants.HEADER_MINIMIZE_RECT.collidepoint(mousePos), Constants.HEADER_CLOSE_RECT.collidepoint(mousePos)
	changed = Runtime.headerMinimizeActive ^ minColl or Runtime.headerCloseActive ^ closeColl 
	Runtime.headerMinimizeActive, Runtime.headerCloseActive = minColl, closeColl
	return changed
def HUDShipboxCollide(mousePos, click=False):
	'''@return - on mouse movement - if changed, on click - shipbox size)'''
	oldHovered = Runtime.shipboxHovered.copy()
	Runtime.shipboxHovered = set()
	changed = False
	for size, rect in Runtime.shipboxRects.items():
		hover = rect.collidepoint(mousePos)
		if hover: Runtime.shipboxHovered.add(size)
		changed |= hover ^ (size in oldHovered)
		if hover and click: return size
	return changed
def HUDReadyCollide(mousePos, click=False) -> bool:
	if Runtime.readyBtnRect is None: return False
	readyHover = Runtime.readyBtnRect.collidepoint(mousePos)
	changed = Runtime.readyBtnHovered ^ readyHover
	Runtime.readyBtnHovered = readyHover
	return changed or (click and readyHover)
def thumbnailCollide(mousePos, click=False):
	hovers = [r.collidepoint(mousePos) for r in Constants.THUMBNAIL_OUTER_RECTS]
	changed = any([old ^ hover for old, hover in zip(Runtime.thumbnailHovers, hovers)])
	Runtime.thumbnailHovers = hovers
	if click: return any(hovers), hovers.index(True) if any(hovers) else None
	return changed

def drawHeader():
	Runtime.display.blit(IMG_HEADER, (0, 0))
	render(FONT_ARIAL17, Constants.HEADER_NAME_POS, 'Battleships', (255, 255, 255) if Runtime.windowHasFocus else (160, 160, 160), fitMode='midleft', antialias=False)
	Runtime.headerMinimizeActive = Constants.HEADER_MINIMIZE_RECT.collidepoint(pygame.mouse.get_pos())
	if Runtime.windowHasFocus and Runtime.headerMinimizeActive:
		pygame.draw.rect(Runtime.display, (140, 140, 140), Constants.HEADER_MINIMIZE_RECT)
	pygame.draw.line(Runtime.display, (255, 255, 255) if Runtime.windowHasFocus else (160, 160, 160), *Constants.HEADER_MINIMIZE_LINE, 3)

	Runtime.headerCloseActive = Constants.HEADER_CLOSE_RECT.collidepoint(pygame.mouse.get_pos())
	if Runtime.windowHasFocus and Runtime.headerCloseActive:
		pygame.draw.rect(Runtime.display, (255, 0, 0), Constants.HEADER_CLOSE_RECT)
	Runtime.display.blit(IMG_HEADER_CROSS if Runtime.windowHasFocus else IMG_HEADER_CROSS_UNFOCUSED, Constants.HEADER_CLOSE_RECT)
def drawHUD():
	assert IMG_HUD is not None
	Runtime.display.blit(IMG_HUD, Constants.HUD_RECT)
def drawThumbnailName(isOpponentGrid: bool, playerName: str, gridRect: pygame.Rect):
	nameColor = (0, 0, 0)
	if Runtime.thumbnailHovers[isOpponentGrid]:
		drawRect(Constants.THUMBNAIL_OUTER_RECTS[isOpponentGrid], (40, 40, 40), border_radius=Constants.THUMBNAIL_MARGIN)
		nameColor = (255, 255, 255)
	render(FONT_ARIAL_MSGS, gridRect.move(0, -2).midtop, playerName, nameColor, fitMode='midbottom')

def drawBackground(offset):
	Runtime.display.blit(IMG_BACKGROUND, (offset, Constants.HEADER_HEIGHT))

def _convertRect(rect, labelDims: pygame.Rect, boundaryPadding, fitMode='topleft') -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
	'''@return: box rect (unpadded), label blit loc, blit area on the label'''
	if isinstance(rect, pygame.Rect) or (isinstance(rect, tuple) and len(rect) == 4):
		rect = pygame.Rect(rect)
		rect.inflate_ip(-2*boundaryPadding, -2*boundaryPadding)
		labelRect = pygame.Rect(0, 0, min(labelDims.w, rect.w), min(labelDims.h, rect.h))
		labelRect.center = rect.center
		labelArea = labelRect.copy()
		labelArea.bottomright = labelDims.bottomright
		return rect, labelRect, labelArea
	boxRect = pygame.Rect(0, 0, *labelDims.bottomright)
	setattr(boxRect, fitMode, rect)
	return boxRect, boxRect.copy(), labelDims
def render(font: pygame.font.Font, rect, text: str, textColor=(0, 0, 0), backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, *, surf=Runtime.display, fitMode='topleft', antialias=True, **rectKwargs) -> pygame.Rect:
	'''
	Draws text, optionally inside rect
	@rect: (x, y) -> @fitMode of text
		(x, y, w, h) -> text centered in rect, if it doesn't fit show the bottom right
	@boundaryPadding: padding between boundary and text, rect size does not change
	@return: text rect
	'''
	label = font.render(text, antialias, textColor)
	boxRect, labelRect, labelArea = _convertRect(rect, label.get_rect(), boundaryPadding, fitMode)
	drawRect(boxRect, backgroundColor, boundaryColor, boundaryWidth, boundaryPadding, surf, **rectKwargs)
	return blit(label, labelRect, area=labelArea, surf=surf)
def blit(img: pygame.Surface, rect, *, rectAttr='topleft', area: pygame.Rect=None, surf=Runtime.display) -> pygame.Rect:
	if isinstance(rect, tuple): rect = pygame.Rect(*rect, 0, 0)
	r = img.get_rect()
	setattr(r, rectAttr, getattr(rect, rectAttr))
	return surf.blit(img, r, area)
def fillColor(color):
	Runtime.display.fill(color)
def drawRect(rect, backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, surf=Runtime.display, **rectArgs):
	if isinstance(rect, tuple): rect = pygame.Rect(*rect)
	rect = rect.inflate(2 * boundaryPadding, 2 * boundaryPadding)
	if backgroundColor: pygame.draw.rect(surf, backgroundColor, rect, **rectArgs)
	if boundaryColor: pygame.draw.rect(surf, boundaryColor, rect, boundaryWidth, **rectArgs)
def drawCircle(color, pos, size):
	pygame.draw.circle(Runtime.display, color, pos, size)
def drawLine(color, start, end, width=1, *, surf=Runtime.display):
	return pygame.draw.line(surf, color, start, end, width)

def update():
	pygame.display.update()
def quit():
	pygame.quit()

# assets + generation ------------------------------------------------------
def genHeader() -> pygame.Surface:
	surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.HEADER_HEIGHT))
	surf.fill((40, 40, 40))
	pygame.draw.lines(surf, (255, 255, 255), False, [(0, 0), (Constants.SCREEN_WIDTH-1, 0), (Constants.SCREEN_WIDTH-1, Constants.HEADER_HEIGHT)])
	surf.blit(loadImage('BattleShips.ico'), (0, 0))
	return surf
def genReadyBtn(iconRect: pygame.Rect, gameStage: STAGES, allShipsPlaced=True):
	readyBtnPos = iconRect.x + Constants.HUD_READY_BTN_DEFAULTS[0], Constants.HUD_READY_BTN_DEFAULTS[1]
	imgIdx = (gameStage == STAGES.GAME_WAIT) + 2 * (gameStage == STAGES.END_GRID_SHOW)
	img = IMG_HUD_READY_BTNS[imgIdx][Runtime.readyBtnHovered] if allShipsPlaced else IMG_HUD_READY_BTNS[-1]
	rect = blit(img, readyBtnPos, rectAttr='bottomleft', surf=IMG_HUD)
	Runtime.readyBtnRect = None
	if not allShipsPlaced and gameStage != STAGES.END_GRID_SHOW: return
	Runtime.readyBtnRect = rect.move(0, Constants.HEADER_HEIGHT - Runtime.readyBtnHovered * 3) # match rect of hovered and normal button
	Runtime.readyBtnRect.h += Runtime.readyBtnHovered * 3
def genPlayerNames(options, gameStage: STAGES) -> list[pygame.Rect]:
	iconRects = [r.copy() for r in Constants.HUD_ICON_RECTS_DEFAULTS]
	leftText = ["Opponent's grid", 'Your grid'][options.myGridShown] if gameStage == STAGES.END_GRID_SHOW else options.submittedPlayerName()
	iconRects[0].x += render(FONT_ARIAL_PLAYERNAME, Constants.HUD_PLAYERNAME_OFFSETS[0], leftText, (255, 255, 255), surf=IMG_HUD).right
	iconRects[1].x += render(FONT_ARIAL_PLAYERNAME, Constants.HUD_PLAYERNAME_OFFSETS[1], options.submittedPlayerName() if gameStage == STAGES.END_GRID_SHOW and options.myGridShown else options.opponentName, (255, 255, 255), surf=IMG_HUD, fitMode='topright').left
	return iconRects
def genIcons(iconRects: list[pygame.Rect], options, gameStage: STAGES, allShipsPlaced, gameWon):
	rightImgMap = {STAGES.SHOOTING: IMG_HUD_AIM if options.myGridShown else IMG_HUD_SHOOTING, STAGES.END_GRID_SHOW: IMG_HUD_GAME_END[gameWon], None: IMG_HUD_READY if options.opponentReady else IMG_HUD_PLACING}
	rightImg = rightImgMap[gameStage if gameStage in rightImgMap else None]
	blit(rightImg, iconRects[1], rectAttr='topright', surf=IMG_HUD)
	if gameStage == STAGES.SHOOTING:
		blit(IMG_HUD_SHOOTING if options.myGridShown else IMG_HUD_AIM, iconRects[0], rectAttr='topleft', surf=IMG_HUD)
	elif gameStage == STAGES.END_GRID_SHOW:
		genReadyBtn(iconRects[0], gameStage)
	else:
		genReadyBtn(iconRects[0], gameStage, allShipsPlaced)
def genShipboxes(shipSizes: dict[int, int], gameStage: STAGES):
	Runtime.shipboxRects = dict()
	if gameStage == STAGES.END_GRID_SHOW and any(shipSizes.values()) == 0: return
	for size, rect in enumerate(Constants.HUD_SHIPBOX_RECTS, 1):
		r = blit(IMG_HUD_SHIPBOXES[size-1], rect, rectAttr='topright', surf=IMG_HUD)
		remaining = shipSizes[size]
		if size in Runtime.shipboxHovered:
			blit(IMG_HUD_SHIPBOXES[4], rect, rectAttr='topright', surf=IMG_HUD)
		if gameStage == STAGES.PLACING and remaining: Runtime.shipboxRects[size] = r.move(0, Constants.HEADER_HEIGHT)
		if size == 4 and remaining == 1: continue
		blit(IMG_HUD_SHIPBOX_COUNTS[remaining], rect, rectAttr='topright', surf=IMG_HUD)
def prepareImgHUD():
	IMG_HUD.fill(COLORKEY)
	drawRect((0, -1, Constants.HUD_RECT.w, Constants.HUD_RECT.h), (40, 40, 40), (255, 255, 255), 2, surf=IMG_HUD, border_bottom_left_radius=Constants.HUD_BOUNDARY_RAD, border_bottom_right_radius=Constants.HUD_BOUNDARY_RAD)
	pygame.draw.line(IMG_HUD, (255, 255, 255), (0, 0), (Constants.HUD_RECT.w, 0), 1)
	IMG_HUD.set_colorkey(COLORKEY)
def genHUD(options, shipSizes: dict[int, int], gameStage: STAGES, gameWon: bool, inTransition: bool):
	prepareImgHUD()
	iconRects = genPlayerNames(options, gameStage)
	if not inTransition: genIcons(iconRects, options, gameStage, sum(shipSizes.values()) == 0, gameWon)
	genShipboxes(shipSizes, gameStage)
def genBackground() -> pygame.Surface:
	cross = loadImage('grid-cross.png')
	surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT - Constants.HEADER_HEIGHT))
	surf.fill((0, 0, 255))
	for y in range(1, Constants.GRID_HEIGHT):
		for x in range(1, Constants.GRID_WIDTH):
			blit(cross, (x * Constants.GRID_X_SPACING, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT), rectAttr='center', surf=surf)
	return surf

IMG_HEADER_CROSS = loadImage('header_close.png')
IMG_HEADER_CROSS_UNFOCUSED = loadImage('header_close_unfocused.png')
IMG_HUD_READY = loadImage('HUD_ready.png')
IMG_HUD_PLACING = loadImage('HUD_placing.png')
IMG_HUD_SHOOTING = loadImage('HUD_shooting.png')
IMG_HUD_AIM = loadImage('HUD_aim.png')
IMG_HUD_READY_BTNS = [[loadImage('Buttons', f'ready_btn_{color}{hover}.png') for hover in ('', '_hover')] for color in ('red', 'green', 'back')] + [loadImage('Buttons', f'ready_btn_unavail.png')]
IMG_HUD_SHIPBOXES = [loadImage('Shipboxes', f'shipbox_{i}.png') for i in range(1, 5)] + [loadImage('Shipboxes', 'shipbox_hovered.png')]
IMG_HUD_SHIPBOX_COUNTS = [loadImage('Shipboxes', f'counts_{i}.png') for i in range(5)]
IMG_HUD_GAME_END = [loadImage(f'HUD_{s}.png') for s in ('lost', 'won')]
IMG_REMATCH = [loadImage('Buttons', f'rematch_btn_{c}.png') for c in ('yellow', 'green', 'red', 'grey')]

IMG_HEADER = genHeader()
IMG_HUD = pygame.Surface((Constants.HUD_RECT.w, Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT))
IMG_BACKGROUND = genBackground()
IMG_TRANSITION = loadImage('transition.png')
