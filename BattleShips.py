import pygame
from Client import Game, Session, Constants

def game():
    pygame.init()
    screen = pygame.display.set_mode((Constants.SCREEN_WIDTH, Constants.SCREEN_HEIGHT))
    sessionObj = Session.Session()
    if pairingWait(screen, sessionObj):
        print(f'[INFO] paired with player id {sessionObj.opponentId}, starting place stage')
        gridObj = Game.Grid()
        if placeStage(screen, sessionObj, gridObj):
            print('[INFO] starting game stage')
            assert False, 'Game stage is not implemented yet'
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
def placeStage(screen: pygame.Surface, sessionObj: Session.Session, gridObj: Game.Grid):
    allPlaced = False
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
                    gridObj.rotateShip()
                if event.key == pygame.K_q:
                    gridObj.removeShipInCursor()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if allPlaced := gridObj.mouseClick(event.pos):
                        sessionObj.sendBoard(gridObj)
                        gameRunning = False
                if event.button == 4: # scroll up
                    gridObj.changeSize(+1)
                elif event.button == 5: # scroll down
                    gridObj.changeSize(-1)

        # connection ---------------------------
        if not sessionObj.ensureConnection():
            gameRunning = False
        # drawing -----------------------------
        screen.fill((255, 255, 255))
        gridObj.drawGrid(screen)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    return allPlaced

if __name__ == '__main__':
    game()