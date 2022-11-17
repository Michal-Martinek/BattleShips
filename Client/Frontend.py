import os, typing, logging
import pygame
from . import Constants
pygame.init()

graphicsDir = os.path.join('Client', 'Graphics')
assert os.path.exists(graphicsDir), 'couldn\'t find the Graphics directory'

# TODO: make the drawing in separate process to save performance and allow easier animations?
# TODO: make animation for the background?
# TODOO: somehow cache the display
class _Frontend:
	COLORKEY = (255, 174, 201)
	def __init__(self):
		self.display: pygame.Surface = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
		self.background = self._genBackground()
		self.errSurf = pygame.Surface((30, 30))
		self.errSurf.fill((255, 0, 0))
		pygame.draw.rect(self.errSurf, (118, 205, 226), (5, 4, 25, 8))
		pygame.draw.rect(self.errSurf, (118, 205, 226), (5, 17, 25, 9))
		self.fonts: dict[str, pygame.font.Font] = {
			'ArialMiddle': pygame.font.SysFont('arial', 40),
			'ArialBig':    pygame.font.SysFont('arial', 60),
			'ArialSmall':  pygame.font.SysFont('arial', 20),
		}
		self.imgs: list[dict[str, list[pygame.Surface]]] = None
		self._loadShips()

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
	def _genBackground(self) -> pygame.Surface:
		cross = self._loadImage(graphicsDir, 'grid-cross.png')
		surf = pygame.Surface((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
		surf.fill((0, 0, 255))
		for row in range(0, Constants.SCREEN_HEIGHT, Constants.GRID_Y_SPACING):
			for col in range(0, Constants.SCREEN_WIDTH, Constants.GRID_X_SPACING):
				crossRect = cross.get_rect()
				crossRect.center = (col - crossRect.width // 2, row - crossRect.height // 2)
				surf.blit(cross, crossRect)
		return surf
	
	def getFrame(self, size: int, horizontal: bool, hitted: list[bool], frame: int) -> pygame.Surface:
		try:
			return self._getFrameWrapper(size, horizontal, hitted, frame)
		except KeyError as e:
			logging.error('Error in generating an animation frame for str') # TODO: when we generate str for cache, use it here
			print(e)
			return self.errSurf.copy()
	# TODO: use some sort of cache for the images
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

	# interface ----------------------
	def blit(self, surf: pygame.Surface, pos: list[int]):
		self.display.blit(surf, pos)
	def fill_color(self, color):
		self.display.fill(color)
	def fill_backgnd(self):
		self.display.blit(self.background, (0, 0))
	def render(self, font:str, pos, text: str, color, antialias=True, backgroundColor=None, boundarySize=0, boundaryColor=None, boundaryPadding=-1):
		label = self.fonts[font].render(text, antialias, color, backgroundColor)
		self.blit(label, pos)
		if boundarySize:
			dims = label.get_rect()
			dims.topleft = pos[0] - boundaryPadding, pos[1] - boundaryPadding
			dims.width += 2 * boundaryPadding
			dims.height += 2 * boundaryPadding
			self.draw_rect(boundaryColor, dims, boundarySize)
	def update(self):
		pygame.display.update()
	def quit(self):
		pygame.quit()

	def draw_rect(self, color, rect, width=0):
		pygame.draw.rect(self.display, color, rect, width)
	def draw_circle(self, color, pos, size):
		pygame.draw.circle(self.display, color, pos, size)
	def draw_line(self, color, start, end, width):
		pygame.draw.line(self.display, color, start, end, width)


Frontend = _Frontend()