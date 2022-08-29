import os, logging
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from . import Constants

pygame.init()
display: pygame.Surface = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
fonts: dict[str, pygame.font.Font] = {
	'ArialMiddle': pygame.font.SysFont('arial', 40),
	'ArialBig':    pygame.font.SysFont('arial', 60),
	'ArialSmall':  pygame.font.SysFont('arial', 20),
}

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
