import os, typing
import logging, traceback
import pygame
from . import Constants
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
FONT_ARIAL_BIG = pygame.font.SysFont('arial', 60)
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
display: pygame.Surface = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT), pygame.NOFRAME)
SDLwindow = Window.from_display_module()
SDLwindow.position = (SDLwindow.position[0], 10)
windowGrabbedPos: list[int, int] = None
headerMinimizeActive = False
headerCloseActive = False
windowHasFocus = True

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
	global windowGrabbedPos
	if mousePos[1] <= Constants.HEADER_HEIGHT:
		windowGrabbedPos = list(mousePos)
		return True
def moveWindow(mousePos):
	SDLwindow.position = SDLwindow.position[0] - windowGrabbedPos[0] + mousePos[0], SDLwindow.position[1] - windowGrabbedPos[1] + mousePos[1]
def headerBtnCollide(mousePos) -> bool:
	global headerMinimizeActive, headerCloseActive
	minColl, closeColl = Constants.HEADER_MINIMIZE_RECT.collidepoint(mousePos), Constants.HEADER_CLOSE_RECT.collidepoint(mousePos)
	changed = headerMinimizeActive ^ minColl or headerCloseActive ^ closeColl 
	headerMinimizeActive, headerCloseActive = minColl, closeColl
	return changed

def drawHeader():
	display.blit(IMG_HEADER, (0, 0))
	render(FONT_ARIAL17, Constants.HEADER_NAME_POS, 'Battleships', (255, 255, 255) if windowHasFocus else (160, 160, 160), fitMode='midleft', antialias=False)
	headerMinimizeActive = Constants.HEADER_MINIMIZE_RECT.collidepoint(pygame.mouse.get_pos())
	if windowHasFocus and headerMinimizeActive:
		pygame.draw.rect(display, (140, 140, 140), Constants.HEADER_MINIMIZE_RECT)
	pygame.draw.line(display, (255, 255, 255) if windowHasFocus else (160, 160, 160), *Constants.HEADER_MINIMIZE_LINE, 3)

	headerCloseActive = Constants.HEADER_CLOSE_RECT.collidepoint(pygame.mouse.get_pos())
	if windowHasFocus and headerCloseActive:
		pygame.draw.rect(display, (255, 0, 0), Constants.HEADER_CLOSE_RECT)
	display.blit(IMG_HEADER_CROSS if windowHasFocus else IMG_HEADER_CROSS_UNFOCUSED, Constants.HEADER_CLOSE_RECT)
def drawHUD():
	assert IMG_HUD is not None
	display.blit(IMG_HUD, Constants.HUD_RECT)
def drawBackground():
	display.blit(IMG_BACKGROUND, (0, Constants.HEADER_HEIGHT))

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
def render(font: pygame.font.Font, rect, text: str, textColor=(0, 0, 0), backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, *, surf=display, fitMode='topleft', antialias=True, **rectKwargs) -> pygame.Rect:
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
def blit(img: pygame.Surface, rect, *, rectAttr='topleft', area: pygame.Rect=None, surf=display) -> pygame.Rect:
	r = img.get_rect()
	setattr(r, rectAttr, getattr(rect, rectAttr))
	return surf.blit(img, r, area)
def fillColor(color):
	display.fill(color)
def drawRect(rect, backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, surf=display, **rectArgs):
	if isinstance(rect, tuple): rect = pygame.Rect(*rect)
	rect.inflate_ip(2 * boundaryPadding, 2 * boundaryPadding)
	if backgroundColor: pygame.draw.rect(surf, backgroundColor, rect, **rectArgs)
	if boundaryColor: pygame.draw.rect(surf, boundaryColor, rect, boundaryWidth, **rectArgs)
def drawCircle(color, pos, size):
	pygame.draw.circle(display, color, pos, size)

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
def _adjustIconVec(iconIdx, nameRect):
	Constants.HUD_ICON_VECS[iconIdx].x += nameRect.right if iconIdx == 0 else nameRect.left
def genHUD(playerName, opponentName):
	IMG_HUD.fill(COLORKEY)
	drawRect((0, -1, Constants.HUD_RECT.w, Constants.HUD_RECT.h), (40, 40, 40), (255, 255, 255), 2, surf=IMG_HUD, border_bottom_left_radius=Constants.HUD_BOUNDARY_RAD, border_bottom_right_radius=Constants.HUD_BOUNDARY_RAD)
	pygame.draw.line(IMG_HUD, (255, 255, 255), (0, 0), (Constants.HUD_RECT.w, 0), 1)

	rect = render(FONT_ARIAL_SMALL, Constants.HUD_PLAYERNAME_OFFSETS[0], playerName, (255, 255, 255), surf=IMG_HUD)
	_adjustIconVec(0, rect)
	rect = render(FONT_ARIAL_SMALL, Constants.HUD_PLAYERNAME_OFFSETS[1], opponentName, (255, 255, 255), surf=IMG_HUD, fitMode='topright')
	_adjustIconVec(1, rect)
	IMG_HUD.set_colorkey(COLORKEY)
def genBackground() -> pygame.Surface:
	cross = loadImage('grid-cross.png')
	surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT - Constants.HEADER_HEIGHT))
	surf.fill((0, 0, 255))
	for y in range(1, Constants.GRID_HEIGHT):
		for x in range(1, Constants.GRID_WIDTH):
			blit(cross, pygame.Rect(x * Constants.GRID_X_SPACING, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT, 0, 0), rectAttr='center', surf=surf)
	pygame.draw.lines(surf, (255, 255, 255), False, [(0, 0), (0, surf.get_height()-1), (Constants.SCREEN_WIDTH-1, surf.get_height()-1), (Constants.SCREEN_WIDTH-1, 0)])
	return surf

IMG_HEADER_CROSS = loadImage('header_close.png')
IMG_HEADER_CROSS_UNFOCUSED = loadImage('header_close_unfocused.png')
IMG_HUD_READY = loadImage('HUD_ready.png')
IMG_HUD_PLACING = loadImage('HUD_placing.png')

IMG_HEADER = genHeader()
IMG_HUD = pygame.Surface((Constants.HUD_RECT.w, Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT))
IMG_BACKGROUND = genBackground()
