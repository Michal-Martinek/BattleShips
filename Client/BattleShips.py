import pygame

from Classes import Game, Session, Constants

def game():
    pygame.init()
    screen = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
    sessionObj = Session.Session()
    if pairingWait(screen, sessionObj):
        print(f'[INFO] paired with player id {sessionObj.opponentId}, starting place stage')
        gameObj = Game.Game()
        placeStage(screen, sessionObj, gameObj)
    sessionObj.close()
    pygame.quit()
def pairingWait(screen: pygame.Surface, sessionObj: Session.Session) -> bool:
    sessionObj.resetTimer()
    clockObj = pygame.time.Clock()
    font = pygame.font.SysFont('arial', 60)
    gameRunning = True
    while gameRunning:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
        if sessionObj.lookForOpponent():
            return True
        screen.fill((255, 255, 255))
        screen.blit(font.render('Waiting for opponent...', True, (0,0,0)), (50, 300))
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    return False
def placeStage(screen: pygame.Surface, sessionObj: Session.Session, gameObj: Game.Game):
    sessionObj.resetTimer()
    clockObj = pygame.time.Clock()
    gameRunning = True
    while gameRunning:
        # controls ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                gameRunning = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    gameObj.rotateFlyingShip()
                if event.key == pygame.K_q:
                    gameObj.removeShipInCursor()
                if event.key == pygame.K_i:
                    print(gameObj.gridObj.shipTypes)
                # if event.key == pygame.K_s:
                    
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    gameObj.mouseClick()
            if event.type == pygame.MOUSEWHEEL:
                gameObj.moveCurrShipType()

        # connection ---------------------------
        if not sessionObj.ensureConnection():
            gameRunning = False
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        gameObj.drawGame(screen)
        pygame.display.update()
        clockObj.tick(Constants.FPS)

if __name__ == '__main__':
    game()