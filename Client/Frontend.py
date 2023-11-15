import os, typing
import logging, traceback
import pygame
from . import Constants
pygame.init()
from pygame._sdl2 import Window

graphicsDir = os.path.join('Client', 'Graphics')
assert os.path.exists(graphicsDir), 'couldn\'t find the Graphics directory'

# TODO: make the drawing in separate process to save performance and allow easier animations?
# TODO: make animation for the background?
class _Frontend:
	COLORKEY = (255, 174, 201)
	def __init__(self):
		self.display: pygame.Surface = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT), pygame.NOFRAME)
		self.SDLwindow = Window.from_display_module()
		self.SDLwindow.position = (self.SDLwindow.position[0], 10)
		self.windowGrabbedPos: list[int, int] = None
		self.headerMinimizeActive = False
		self.headerCloseActive = False
		self.windowHasFocus = True
		
		self.headerCross = self._loadImage(graphicsDir, 'header_close.png')
		self.headerCrossUnfocused = self._loadImage(graphicsDir, 'header_close_unfocused.png')
		self.errSurf = pygame.Surface((30, 30))
		self.errSurf.fill((255, 0, 0))
		pygame.draw.rect(self.errSurf, (118, 205, 226), (5, 4, 25, 8))
		pygame.draw.rect(self.errSurf, (118, 205, 226), (5, 17, 25, 9))
		self.fonts: dict[str, pygame.font.Font] = {
			'ArialMiddle': pygame.font.SysFont('arial', 40),
			'ArialBig':    pygame.font.SysFont('arial', 60),
			'ArialSmall':  pygame.font.SysFont('arial', 20),
			'ArialHeader': pygame.font.SysFont('arial', 17),
		}
		self.imgs: list[dict[str, list[pygame.Surface]]] = None
		self._loadShips()
		self.frameCache: dict[str, pygame.Surface] = dict()

		self.header = self._genHeader()
		self.HUD = self._genHUD()
		self.background = self._genBackground()

	# images --------------------------------------------
	def _loadImage(self, dir, file):
		try:
			img = pygame.image.load(os.path.join(dir, file)).convert()
		except FileNotFoundError:
			logging.error(f'The image {file} in {dir} could not be found')
			img = self.errSurf.copy()
		img.set_colorkey(self.COLORKEY)
		return img
	def _loadFrames(self, dir, format: str, options: list[str], numerator:typing.Iterable) -> dict[str, list[pygame.Surface]]:
		d = dict()
		for option in options:
			d[option] = [self._loadImage(dir, format.format(option=option, n=n)) for n in numerator]
		return d
	def _loadShips(self):
		self.imgs = [
			self._loadFrames(os.path.join(graphicsDir, 'Ships', '1-ship'), '{option}_{n}.png', ['HA', 'HD', 'VA', 'VD'], range(1, 4)),
			self._loadFrames(os.path.join(graphicsDir, 'Ships', '2-ship'), '{option}_{n}.png', ['HAL', 'HAR', 'HDL', 'HDR', 'HDLR', 'VAB', 'VAT', 'VDB', 'VDT', 'VDTB'], range(1, 4)),
			self._loadFrames(os.path.join(graphicsDir, 'Ships', '3-ship'), '{option}_{n}.png', ['HAL', 'HAR', 'HDL_L', 'HDL_M', 'HDL_LM', 'HDR_M', 'HDR_R', 'HDR_MR', 'VAT', 'VAB', 'VDT', 'VDB_M', 'VDB_B', 'VDB_MB', 'VD_TMB'], range(1, 4)),
			self._loadFrames(os.path.join(graphicsDir, 'Ships', '4-ship'), '{option}_{n}.png', ['HAL', 'HAR', 'HDL_L', 'HDL_R', 'HDL_LR', 'HDR_L', 'HDR_R', 'HDR_LR', 'HDA', 'VAT', 'VAB', 'VDT_T', 'VDT_B', 'VDT_TB', 'VDB_T', 'VDB_B', 'VDB_TB', 'VDA'], range(1, 4)),
		]
	def _getFrameStrings(self, size, horizontal, hitted) -> tuple[list[str], tuple[int]]:
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
	def _mergeImgs(self, surf1, surf2, horizontal: bool, verticalOffsets) -> pygame.Surface:
		if horizontal:
			s = pygame.Surface((surf1.get_width() + surf2.get_width(), max(surf1.get_height(), surf2.get_height())))
			s.fill(self.COLORKEY)
			s.blit(surf1, (0, max(0, surf2.get_height() - surf1.get_height())))
			s.blit(surf2, (surf1.get_width(), max(0, surf1.get_height() - surf2.get_height())))
			s.set_colorkey(self.COLORKEY)
			return s
		else:
			s = pygame.Surface((max(surf1.get_width(), surf2.get_width()), surf1.get_height() + surf2.get_height() - verticalOffsets[2]))
			s.fill(self.COLORKEY)
			s.blit(surf1, (max(0, verticalOffsets[1] - verticalOffsets[0]), 0))
			s.blit(surf2, (max(0, verticalOffsets[0] - verticalOffsets[1]), surf1.get_height() - verticalOffsets[2]))
			s.set_colorkey(self.COLORKEY)
			return s
	def _blitPositioned(self, surf, rectAttr, rectVal, img):
		if not isinstance(img, pygame.Surface):
			img = self._loadImage(graphicsDir, img)
		rect = img.get_rect()
		setattr(rect, rectAttr, rectVal)
		surf.blit(img, rect)
	def _genHeader(self) -> pygame.Surface:
		surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.HEADER_HEIGHT))
		surf.fill((40, 40, 40))
		pygame.draw.lines(surf, (255, 255, 255), False, [(0, 0), (Constants.SCREEN_WIDTH-1, 0), (Constants.SCREEN_WIDTH-1, Constants.HEADER_HEIGHT)])
		surf.blit(self._loadImage(graphicsDir, 'BattleShips.ico'), (0, 0))
		return surf
	def _genHUD(self) -> pygame.Surface:
		surf = pygame.Surface((Constants.HUD_RECT.w, Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT))
		surf.fill(self.COLORKEY)
		self.draw_rect((0, -1, Constants.HUD_RECT.w, Constants.HUD_RECT.h), (40, 40, 40), (255, 255, 255), 2, surf=surf, border_bottom_left_radius=Constants.HUD_BOUNDARY_RAD, border_bottom_right_radius=Constants.HUD_BOUNDARY_RAD)
		pygame.draw.line(surf, (255, 255, 255), (0, 0), (Constants.HUD_RECT.w, 0), 1)
		surf.set_colorkey(self.COLORKEY)
		return surf
	def _genBackground(self) -> pygame.Surface:
		cross = self._loadImage(graphicsDir, 'grid-cross.png')
		surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT - Constants.HEADER_HEIGHT))
		surf.fill((0, 0, 255))
		for y in range(1, Constants.GRID_HEIGHT):
			for x in range(1, Constants.GRID_WIDTH):
				crossRect = cross.get_rect()
				crossRect.center = x * Constants.GRID_X_SPACING - crossRect.width // 2, y * Constants.GRID_Y_SPACING - crossRect.height // 2 + Constants.GRID_Y_OFFSET - Constants.HEADER_HEIGHT
				surf.blit(cross, crossRect)
		pygame.draw.lines(surf, (255, 255, 255), False, [(0, 0), (0, surf.get_height()-1), (Constants.SCREEN_WIDTH-1, surf.get_height()-1), (Constants.SCREEN_WIDTH-1, 0)])
		return surf
	
	def getFrame(self, size: int, horizontal: bool, hitted: list[bool], frame: int) -> pygame.Surface:
		cacheStr = str(size) + '-' + str(int(horizontal)) + '-' + ''.join([str(int(x)) for x in hitted]) + '-' + str(frame)
		if cacheStr in self.frameCache:
			return self.frameCache[cacheStr]
		try:
			frame = self._getFrameWrapper(size, horizontal, hitted, frame)
		except KeyError as e:
			logging.error(f'failed to generate animation frame for {cacheStr}: ' + traceback.format_exception(type(e), e, None)[0][:-1])
			frame = self.errSurf.copy()
		self.frameCache[cacheStr] = frame
		return frame
	def _getFrameWrapper(self, size, horizontal, hitted, frame):
		out = self._getFrameStrings(size, horizontal, hitted)
		if isinstance(out, tuple):
			strs, offsets = out
		else:
			strs = out
			offsets = (0, 0, 0)
		if len(strs) == 1: return self.imgs[size-1][strs[0]][frame]
		if len(strs) == 2:
			return self._mergeImgs(self.imgs[size-1][strs[0]][frame], self.imgs[size-1][strs[1]][frame], horizontal, offsets)
		return self.errSurf.copy()

	@staticmethod
	def _convertRect(rect, labelDims: pygame.Rect, boundaryPadding, fitMode='topleft') -> tuple[pygame.Rect, pygame.Rect]:
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
	# interface ----------------------
	def blit(self, surf: pygame.Surface, pos: list[int], area: pygame.Rect=None):
		self.display.blit(surf, pos, area)
	def fill_color(self, color):
		self.display.fill(color)
	def draw_header(self):
		self.display.blit(self.header, (0, 0))
		label = self.fonts['ArialHeader'].render('Battleships', False, (255, 255, 255) if self.windowHasFocus else (160, 160, 160))
		self._blitPositioned(self.display, 'midleft', Constants.HEADER_NAME_POS, label)

		self.headerMinimizeActive = Constants.HEADER_MINIMIZE_RECT.collidepoint(pygame.mouse.get_pos())
		if self.windowHasFocus and self.headerMinimizeActive:
			pygame.draw.rect(self.display, (140, 140, 140), Constants.HEADER_MINIMIZE_RECT)
		self.draw_line((255, 255, 255) if self.windowHasFocus else (160, 160, 160), *Constants.HEADER_MINIMIZE_LINE, 3)

		self.headerCloseActive = Constants.HEADER_CLOSE_RECT.collidepoint(pygame.mouse.get_pos())
		if self.windowHasFocus and self.headerCloseActive:
			pygame.draw.rect(self.display, (255, 0, 0), Constants.HEADER_CLOSE_RECT)
		self.display.blit(self.headerCross if self.windowHasFocus else self.headerCrossUnfocused, Constants.HEADER_CLOSE_RECT)
	def drawHUD(self, playerName, opponentName):
		self.display.blit(self.HUD, Constants.HUD_RECT)
		self.render('ArialSmall', Constants.HUD_PLAYERNAME_OFFSETS[0], playerName, (255, 255, 255), fitMode='topleft')
		self.render('ArialSmall', Constants.HUD_PLAYERNAME_OFFSETS[1], opponentName, (255, 255, 255), fitMode='topright')
	def fill_backgnd(self):
		self.display.blit(self.background, (0, Constants.HEADER_HEIGHT))
	def render(self, font:str, rect, text: str, textColor=(0, 0, 0), backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, *, fitMode='topleft', **rectKwargs):
		'''
		Draws text, optionally inside rect
		@rect: (x, y) -> <fitMode> of text
			(x, y, w, h) -> text centered in rect, if it doesn't fit show the bottom right
		@boundaryPadding: padding between boundary and text, rect size does not change
		'''
		label = self.fonts[font].render(text, True, textColor)
		boxRect, labelRect, labelArea = self._convertRect(rect, label.get_rect(), boundaryPadding, fitMode)
		self.draw_rect(boxRect, backgroundColor, boundaryColor, boundaryWidth, boundaryPadding, **rectKwargs)
		self.blit(label, labelRect, labelArea)

	def update(self):
		pygame.display.update()
	def quit(self):
		pygame.quit()
	def grabWindow(self, mousePos):
		if mousePos[1] <= Constants.HEADER_HEIGHT:
			self.windowGrabbedPos = list(mousePos)
			return True
	def moveWindow(self, mouseRel):
		self.SDLwindow.position = self.SDLwindow.position[0] - self.windowGrabbedPos[0] + mouseRel[0], self.SDLwindow.position[1] - self.windowGrabbedPos[1] + mouseRel[1]
	def draw_rect(self, rect, backgroundColor=None, boundaryColor=None, boundaryWidth=0, boundaryPadding=0, surf=None, **kwargs):
		if isinstance(rect, tuple): rect = pygame.Rect(*rect)
		rect.inflate_ip(2 * boundaryPadding, 2 * boundaryPadding)
		if not surf: surf = self.display
		if backgroundColor: pygame.draw.rect(surf, backgroundColor, rect, **kwargs)
		if boundaryColor: pygame.draw.rect(surf, boundaryColor, rect, boundaryWidth, **kwargs)
	def draw_circle(self, color, pos, size):
		pygame.draw.circle(self.display, color, pos, size)
	def draw_line(self, color, start, end, width):
		pygame.draw.line(self.display, color, start, end, width)


Frontend = _Frontend()