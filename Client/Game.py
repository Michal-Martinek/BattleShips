import pygame, logging
from . import Constants
from .Session import Session

class Game:
    def __init__(self):
        self.session = Session()
        logging.info(f'connected to the server, id={self.session.id}')
        self.grid = Grid()
        self.readyForGame: bool = False # signalizes that the player has done playcing the ships and wants to start the game
        self.opponentsGrid = None
    def newGameStage(self):
        self.session.resetAllTimers()
    def sendReadyForGame(self):
        state =  {'ready': self.readyForGame, 'ships': self.grid.shipsDicts()}
        self.session.sendReadyForGame(state)
    def rotateShip(self):
        self.grid.rotateShip()
    def removeShipInCursor(self):
        self.grid.removeShipInCursor()
    def mouseClick(self, mousePos):
        if not self.readyForGame:
            self.grid.mouseClick(mousePos)
            if self.allShipsPlaced():
                self.toggleGameReady()
    def changeShipSize(self, increment: int):
        self.grid.changeSize(increment)
    def drawGame(self, window, font):
        self.grid.drawGrid(window)
        if self.readyForGame:
            surf = font.render('Waiting for the other player to place ships...', True, (0, 0, 0), (255, 255, 255))
            pygame.draw.rect(window, (0, 0, 0), (25, 200, surf.get_width(), surf.get_height()), 5)
            window.blit(surf, (25, 200))
    def quit(self):
        self.session.close()
    def allShipsPlaced(self):
        return self.grid.allShipsPlaced()
    def toggleGameReady(self):
        if self.readyForGame or self.allShipsPlaced():
            self.newGameStage()
            self.readyForGame = not self.readyForGame
            self.sendReadyForGame()
            logging.info('all ships placed, sending ready for game to the server')
    def waitForGame(self) -> bool:
        info = self.session.waitForGame()
        if info:
            self.opponentsGrid = Grid.fromShipsDicts(info['ships'])
            return False
        return True
    def lookForOpponent(self):
        return self.session.lookForOpponent()
    def ensureConnection(self):
        return self.session.ensureConnection()

class Grid:
    def __init__(self):
        self.shipSizes: dict[int, int] = {1: 2, 2: 4, 3: 2, 4: 1} # shipSize : shipCount
        self.flyingShip: Ship = Ship([-1, -1], 0, True)
        self.placedShips: list[Ship] = []

    def shipsDicts(self):
        return [ship.asDict() for ship in self.placedShips]
    @ classmethod
    def fromShipsDicts(cls, dicts: list[dict]):
        grid = Grid()
        grid.placedShips = [Ship.fromDict(d) for d in dicts]
        return grid
    def allShipsPlaced(self):
            return not any(self.shipSizes.values()) 

    def rotateShip(self):
        self.flyingShip.horizontal = not self.flyingShip.horizontal
    def removeShipInCursor(self):
        self.flyingShip.size = 0

    def mouseClick(self, mousePos):
        if self.flyingShip.size == 0:
            self.pickUpShip(mousePos)
        else:
            self.placeShip()
    def canPlaceShip(self, placed):
        gridRect = pygame.Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT)
        if not gridRect.contains(placed.getOccupiedRect()):
            return False
        for ship in self.placedShips:
            if placed.isColliding(ship):
                return False
        return True

    def placeShip(self):
        placed = self.flyingShip.getPlacedShip()
        if self.canPlaceShip(placed):   
            self.placedShips.append(placed)
            self.shipSizes[placed.size] -= 1
            self.changeSize(+1, canBeSame=True)

    def pickUpShip(self, mousePos):
        for ship in self.placedShips:
            if ship.realRect.collidepoint(mousePos):
                self._pickUpClickedShip(ship)
                break
    def _pickUpClickedShip(self, ship):
        self.flyingShip = ship.getFlying()
        self.placedShips.remove(ship)
        self.shipSizes[ship.size] += 1

    def _nextShipSize(self, startSize, increment):
        currSize = startSize + increment
        while currSize not in self.shipSizes:
            if currSize == startSize: break
            currSize += increment
            currSize = currSize % (max(self.shipSizes.keys()) + 1)
        return currSize
    def changeSize(self, increment: int, *, canBeSame=False):
        currSize = self.flyingShip.size
        if not canBeSame:
            currSize = self._nextShipSize(currSize, increment)
        while self.shipSizes[currSize] == 0:
            currSize = self._nextShipSize(currSize, increment)
            if currSize == self.flyingShip.size:
                if self.shipSizes[currSize] == 0:
                    self.removeShipInCursor()
                return
        self.flyingShip.size = currSize
    
    def drawGrid(self, window):
        self.drawGridlines(window)
        for ship in self.placedShips:
            ship.draw(window)
        if self.flyingShip.size:
            self.flyingShip.draw(window)
    def drawGridlines(self, window):
        for row in range(Constants.GRID_HEIGHT):
            yCoord = Constants.GRID_Y_SPACING * row
            pygame.draw.line(window, (0, 0, 0), (0, yCoord), (Constants.SCREEN_WIDTH, yCoord))
        for col in range(Constants.GRID_WIDTH):
            xCoord = Constants.GRID_X_SPACING * col
            pygame.draw.line(window, (0, 0, 0), (xCoord, 0), (xCoord, Constants.SCREEN_HEIGHT))


class Ship:
    def __init__(self, pos: list, size, horizontal):
        self.pos: list[int] = pos
        self.size: int = size
        self.horizontal: bool = horizontal
    
    def asDict(self):
        return {'pos': self.pos, 'size': self.size, 'horizontal': self.horizontal}
    @ classmethod
    def fromDict(self, d: dict):
        return Ship(d['pos'], d['size'], d['horizontal'])

    def getFlying(self):
        return Ship([-1, -1], self.size, self.horizontal)
    def getPlacedShip(self):
        assert self.pos == [-1, -1], 'only ship which is flying can be placed'
        realX, realY = self.realPos
        x = realX // Constants.GRID_X_SPACING
        x += (realX % Constants.GRID_X_SPACING) > (Constants.GRID_X_SPACING // 2)
        y = realY // Constants.GRID_Y_SPACING
        y += (realY % Constants.GRID_Y_SPACING) > (Constants.GRID_Y_SPACING // 2)
        return Ship([x, y], self.size, self.horizontal)

    @ property
    def widthInGrid(self):
        return (self.size - 1) * self.horizontal + 1
    @ property
    def heightInGrid(self):
        return (self.size - 1) * (not self.horizontal) + 1
    @ property
    def realPos(self):
        if self.pos == [-1, -1]:
            mouseX, mouseY = pygame.mouse.get_pos()
            return mouseX - self.widthInGrid * Constants.GRID_X_SPACING // 2, mouseY - self.heightInGrid * Constants.GRID_Y_SPACING // 2
        else:
            return self.pos[0] * Constants.GRID_X_SPACING, self.pos[1] * Constants.GRID_Y_SPACING
    @ property
    def realRect(self):
        '''Rect of real ship coordinates'''
        return pygame.Rect(*self.realPos, self.widthInGrid * Constants.GRID_X_SPACING, self.heightInGrid * Constants.GRID_Y_SPACING)
    
    def getRealSegmentCoords(self):
        '''returns list of real coords of all ship segments'''
        segments = []
        realX, realY = self.realPos
        for i in range(self.size):
            segments.append([realX, realY])
            realX += Constants.GRID_X_SPACING * self.horizontal
            realY += Constants.GRID_Y_SPACING * (not self.horizontal)
        return segments

    def getnoShipsRect(self):
        return pygame.Rect(self.pos[0] - 1, self.pos[1] - 1,  self.widthInGrid + 2, self.heightInGrid + 2)
    def getOccupiedRect(self):
        return pygame.Rect(self.pos[0], self.pos[1], self.widthInGrid, self.heightInGrid)
    def isColliding(self, other):
        '''checks if other collides with the noShipsRect of self'''
        return self.getnoShipsRect().colliderect(other.getOccupiedRect())
    
    def draw(self, window):
        for x, y in self.getRealSegmentCoords():
            pygame.draw.rect(window, (0, 0, 0), (x, y, Constants.GRID_X_SPACING, Constants.GRID_Y_SPACING), 1)
        pygame.draw.rect(window, (0, 0, 0), self.realRect, 4)
