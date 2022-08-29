import os, sys
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import logging
from Client import Game, Constants
from Shared.Enums import STAGES

def game():
    pygame.init()
    logging.basicConfig(level=logging.INFO)
    screen = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
    game = Game.Game(screen)

    clockObj = pygame.time.Clock()
    # TODO: autoplace
    # TODO: timer for close: pygame.time.set_timer(pygame.USEREVENT, 5000, loops=1)
    while game.gameStage != STAGES.CLOSING or not game.session.properlyClosed:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.newGameStage(STAGES.CLOSING)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.rotateShip()
                if event.key == pygame.K_q:
                    game.changeCursor()
                if event.key == pygame.K_g:
                    game.toggleGameReady()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    game.mouseClick(event.pos, rightClick=False)
                elif event.button == 3:
                    game.mouseClick(event.pos, rightClick=True)
                elif event.button == 4: # scroll up
                    game.changeShipSize(+1)
                elif event.button == 5: # scroll down
                    game.changeShipSize(-1)
        
        game.tryRequests()
        if game.gameStage in [STAGES.PLACING, STAGES.SHOOTING, STAGES.GETTING_SHOT]:
            screen.fill((255, 255, 255))
        game.drawGame(screen)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
        
    pygame.quit()

if __name__ == '__main__':
    game()