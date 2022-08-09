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
    gameExited = True

    if pairingWait(screen, game):
        logging.info(f'paired, starting place stage')
        startShooting, gameExited = placeStage(screen, game)
        if startShooting and not gameExited:
            logging.info('starting shooting stage')
            gameExited = shootingStage(screen, game)
    
    game.quit()
    if not gameExited:
        endingScreen(screen, game.gameStage == STAGES.WON)
    pygame.quit()
def pairingWait(screen: pygame.Surface, game: Game.Game) -> bool:
    clockObj = pygame.time.Clock()
    # drawing
    font = pygame.font.SysFont('arial', 60)
    screen.fill((255, 255, 255))
    screen.blit(font.render('Waiting for opponent...', True, (0,0,0)), (50, 300))
    pygame.display.update()

    gameRunning = True
    while gameRunning and game.gameStage != STAGES.PLACING:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
        game.tryRequests()
        clockObj.tick(Constants.FPS)
    return game.gameStage == STAGES.PLACING
def placeStage(screen: pygame.Surface, game: Game.Game):
    if '--autoplace' in sys.argv:
        game.autoplace()
    
    font = pygame.font.SysFont('arial', 40)
    clockObj = pygame.time.Clock()

    exited = False
    while game.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT]:
        # controls ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.newGameStage(STAGES.CLOSING)
                exited = True
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
    return game.gameStage in [STAGES.SHOOTING, STAGES.GETTING_SHOT], exited
def shootingStage(screen: pygame.Surface, game: Game.Game) -> tuple[bool, bool]:
    clockObj = pygame.time.Clock()
    exited = False
    gameRunning = True
    while gameRunning:
        # controls ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
                game.newGameStage(STAGES.CLOSING)
                exited = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if game.shoot(event.pos):
                        gameRunning = False

        # connection ---------------------------
        game.tryRequests()
        if game.gameStage in [STAGES.WON, STAGES.LOST]:
            gameRunning = False
        
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        if game.gameStage == STAGES.SHOOTING:
            game.drawOnTurn(screen)
        else:
            game.drawOutTurn(screen)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    return exited

def endingScreen(screen: pygame.Surface, gameWon: bool):
    clockObj = pygame.time.Clock()
    font = pygame.font.SysFont('arial', 60)

    # drawing the message
    message = ['You lost!   :(', 'You won!   :)'][gameWon]
    screen.fill((255, 255, 255))
    screen.blit(font.render(message, True, (0,0,0)), (150, 300))
    pygame.display.update()

    time = 0
    while time <= Constants.FPS * 5:
        for event in pygame.event.get():
            if event.type in [pygame.QUIT, pygame.KEYDOWN]:
                return
        time += 1
        clockObj.tick(Constants.FPS)


if __name__ == '__main__':
    game()