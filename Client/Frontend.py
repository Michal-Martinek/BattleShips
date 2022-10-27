import os, logging
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from . import Constants

# TODO: make the drawing in separate process to save performance and allow easier animations?
graphicsDir = os.path.join('Client', 'Graphics')

pygame.init()
display: pygame.Surface = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
fonts: dict[str, pygame.font.Font] = {
	'ArialMiddle': pygame.font.SysFont('arial', 40),
	'ArialBig':    pygame.font.SysFont('arial', 60),
	'ArialSmall':  pygame.font.SysFont('arial', 20),
}
def loadImages(names, subdir='', colorkey=(255, 174, 201)) -> list[pygame.Surface]:
	imgs = []
	for name in names:
		img = pygame.image.load(os.path.join(graphicsDir, subdir, name))
		img.set_colorkey(colorkey)
		imgs.append(img)
	return imgs
# TODO: resize the images to fit them better on the screen
images = loadImages(['ship-1V.png', 'ship-2V.png', 'ship-3V.png', 'ship-4V.png', 'ship-1H.png', 'ship-2H.png', 'ship-3H.png', 'ship-4H.png'], subdir='Ships')
cross = loadImages(['grid-cross.png'])[0]

class draw:
	@ staticmethod
	def rect(color, rect, width=0):
		pygame.draw.rect(display, color, rect, width)
	@ staticmethod
	def circle(color, pos, size):
		pygame.draw.circle(display, color, pos, size)
	@ staticmethod
	def line(color, start, end, width):
		pygame.draw.line(display, color, start, end, width)


def blit(surf: pygame.Surface, pos: list[int]):
	display.blit(surf, pos)
def fill(color):
	display.fill(color)
def render(font:str, pos, text: str, color, antialias=True, backgroundColor=None, boundarySize=0, boundaryColor=None, boundaryPadding=-1):
	label = fonts[font].render(text, antialias, color, backgroundColor)
	blit(label, pos)
	if boundarySize:
		dims = label.get_rect()
		dims.topleft = pos[0] - boundaryPadding, pos[1] - boundaryPadding
		dims.width += 2 * boundaryPadding
		dims.height += 2 * boundaryPadding
		draw.rect(boundaryColor, dims, boundarySize)
def update():
	pygame.display.update()
def quit():
	pygame.quit()
