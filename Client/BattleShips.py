import pygame

from Classes import Game, Session, Constants

def game():
    gameObj = Game.Game()
    clockObj = pygame.time.Clock()
    sessionObj = Session.Session()
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
        sessionObj.handleConn()
        # drawing -----------------------------
        Constants.SCREEN.fill((255, 255, 255))
        gameObj.drawGame(Constants.SCREEN)
        pygame.display.update()
        clockObj.tick(Constants.FPS)
    sessionObj.close()

if __name__ == '__main__':
    game()