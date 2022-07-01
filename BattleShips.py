import pygame
import logging
from Client import Game, Constants

def game():
    pygame.init()
    logging.basicConfig(level=logging.INFO)
    screen = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))

    game = Game.Game()
    if pairingWait(screen, game):
        logging.info(f'paired with player id {game.session.opponentId}, starting place stage')
        if placeStage(screen, game):
            logging.info('starting game stage')
            game.quit()
            assert False, 'Game stage is not implemented yet'

    game.quit()
    pygame.quit()
def pairingWait(screen: pygame.Surface, game: Game.Game) -> bool:
    game.newGameStage()
    clockObj = pygame.time.Clock()
    font = pygame.font.SysFont('arial', 60)
    gameRunning = True
    while gameRunning:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
        if game.lookForOpponent():
            return True
        screen.fill((255, 255, 255))
        screen.blit(font.render('Waiting for opponent...', True, (0,0,0)), (50, 300))
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    return False
def placeStage(screen: pygame.Surface, game: Game.Game):
    game.newGameStage()
    font = pygame.font.SysFont('arial', 40)
    clockObj = pygame.time.Clock()

    exited = False
    gameRunning = True
    while gameRunning:
        # controls ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
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
        if not game.ensureConnection():
            gameRunning = False
        if game.readyForGame and gameRunning:
            gameRunning = game.waitForGame()
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        game.drawGame(screen, font)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    return game.readyForGame and not exited

if __name__ == '__main__':
    game()