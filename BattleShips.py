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
    game = Game.Game()

    pairingWait(screen, game)
    if game.gameStage == STAGES.PLACING:
        logging.info(f'paired, starting place stage')
        placeStage(screen, game)
        if game.gameStage in [STAGES.SHOOTING, STAGES.GETTING_SHOT]:
            logging.info('starting shooting stage')
            shootingStage(screen, game)
    
    endingScreen(screen, game)
    pygame.quit()
def pairingWait(screen: pygame.Surface, game: Game.Game) -> bool:
    clockObj = pygame.time.Clock()
    # drawing
    font = pygame.font.SysFont('arial', 60)
    screen.fill((255, 255, 255))
    screen.blit(font.render('Waiting for opponent...', True, (0,0,0)), (50, 300))
    pygame.display.update()

    while game.gameStage in [STAGES.PAIRING, STAGES.CONNECTING]:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.newGameStage(STAGES.CLOSING)
        game.tryRequests()
        clockObj.tick(Constants.FPS)
def placeStage(screen: pygame.Surface, game: Game.Game):
    if '--autoplace' in sys.argv:
        game.autoplace()
    
    font = pygame.font.SysFont('arial', 40)
    clockObj = pygame.time.Clock()

    while game.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT]:
        # controls ------------------------------
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

        # connection ---------------------------
        game.tryRequests()
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        game.drawGame(screen, font)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
def shootingStage(screen: pygame.Surface, game: Game.Game) -> tuple[bool, bool]:
    clockObj = pygame.time.Clock()
    while game.gameStage in [STAGES.SHOOTING, STAGES.GETTING_SHOT]:
        # controls ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.newGameStage(STAGES.CLOSING)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    game.shoot(event.pos)

        # connection ---------------------------
        game.tryRequests()
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        if game.gameStage == STAGES.SHOOTING:
            game.drawOnTurn(screen)
        elif game.gameStage == STAGES.GETTING_SHOT:
            game.drawOutTurn(screen)
        pygame.display.update()
        clockObj.tick(Constants.FPS)

def endingScreen(screen: pygame.Surface, game: Game.Game):
    clockObj = pygame.time.Clock()
    font = pygame.font.SysFont('arial', 60)

    # drawing the message
    message = ['You lost!   :(', 'You won!   :)'][game.gameStage == STAGES.WON]
    screen.fill((255, 255, 255))
    if game.gameStage in [STAGES.WON, STAGES.LOST]:
        screen.blit(font.render(message, True, (0,0,0)), (150, 300))
    pygame.display.update()

    pygame.time.set_timer(pygame.USEREVENT, 5000, loops=1)
    while game.gameStage != STAGES.CLOSING or not game.session.properlyClosed:
        for event in pygame.event.get():
            if event.type in [pygame.QUIT, pygame.KEYDOWN, pygame.USEREVENT]:
                if game.gameStage != STAGES.CLOSING:
                    game.newGameStage(STAGES.CLOSING)
        game.tryRequests()
        clockObj.tick(Constants.FPS)


if __name__ == '__main__':
    game()