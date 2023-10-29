import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import logging
from Client import Game, Constants
from Shared.Enums import STAGES
from Shared.Helpers import runFuncLogged

def game():
    if not os.path.exists('logs'): os.mkdir('logs')
    logging.basicConfig(filename=os.path.join('logs', 'client_log.txt'), level=logging.INFO, format='[%(levelname)s] %(asctime)s %(threadName)s:%(module)s:%(funcName)s:    %(message)s')
    pygame.fastevent.init()
    pygame.time.set_timer(pygame.event.Event(pygame.USEREVENT), Constants.ANIMATION_TIMING)
    
    game = Game.Game()

    clockObj = pygame.time.Clock()
    while game.gameStage != STAGES.CLOSING or not game.session.properlyClosed:
        for event in pygame.fastevent.get():
            if event.type == pygame.QUIT:
                logging.info('Closing due to client quit')
                game.newGameStage(STAGES.CLOSING)
            elif event.type == pygame.USEREVENT:
                game.advanceAnimations()
            elif event.type == pygame.KEYDOWN:
                if game.gameStage in [STAGES.WON, STAGES.LOST]:
                    game.newGameStage(STAGES.CLOSING)
                elif event.key == pygame.K_r:
                    game.rotateShip()
                elif event.key == pygame.K_q:
                    game.changeCursor()
                elif event.key == pygame.K_g:
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
        
        game.handleRequests()
        game.drawGame()
        if game.gameStage != STAGES.CLOSING: clockObj.tick(Constants.FPS)

def main():
    runFuncLogged(game)
if __name__ == '__main__':
    main()
