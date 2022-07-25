import pygame, logging
from . import Constants
from .Session import Session

class Game:
    def __init__(self):
        self.session = Session()
        logging.info(f'connected to the server, id={self.session.id}')
        self.grid = Grid()
        self.readyForGame: bool = False
        self.onTurn: bool = False
    def newGameStage(self):
        self.session.resetAllTimers()
    def sendReadyForGame(self) -> bool:
        state =  {'ready': not self.readyForGame, 'ships': self.grid.shipsDicts()}
        return self.session.sendReadyForGame(state)
    def rotateShip(self):
        self.grid.rotateShip()
    def changeCursor(self):
        if not self.grid.allShipsPlaced():
            self.grid.changeCursor(pygame.mouse.get_pos())
    def mouseClick(self, mousePos, rightClick):
        if not self.readyForGame:
            changed = self.grid.mouseClick(mousePos, rightClick)
            if changed:
                self.toggleGameReady()
    def changeShipSize(self, increment: int):
        if not self.grid.allShipsPlaced():
            self.grid.changeSize(increment)
    def drawGame(self, window, font):
        self.grid.drawGrid(window)
        if self.readyForGame:
            surf = font.render('Waiting for the other player to place ships...', True, (0, 0, 0), (255, 255, 255))
            pygame.draw.rect(window, (0, 0, 0), (25, 200, surf.get_width(), surf.get_height()), 5)
            window.blit(surf, (25, 200))
    def drawOnTurn(self, window):
        self.grid.drawShotted(window)
    def drawOutTurn(self, window):
        self.grid.drawGrid(window)

    def autoplace(self):
        assert not self.readyForGame
        self.grid.autoplace()
        self.toggleGameReady()
        assert self.readyForGame
    def quit(self):
        self.session.close()
    def toggleGameReady(self):
        if self.grid.allShipsPlaced():
            approved = self.sendReadyForGame()
            if approved:
                self.newGameStage()
                self.readyForGame = not self.readyForGame
                logging.debug('toggling readyForGame')
    def waitForGame(self) -> bool:
        started, onTurn = self.session.waitForGame()
        if started:
            self.onTurn = onTurn
        return not started
    def opponentShot(self) -> bool:
        pos, lost = self.session.opponentShot()
        if pos is not None:
            self.grid.opponentShot(pos)
            self.onTurn = True
        return lost
    def shoot(self, mousePos) -> bool:
        if self.onTurn:
            gridPos = self.grid.shoot(mousePos)
            if gridPos:
                hitted, wholeShip, gameWon = self.session.shoot(gridPos)
                self.grid.updateHitted(gridPos, hitted, wholeShip)
                self.onTurn = False
                return gameWon
        return False
    def lookForOpponent(self):
        return self.session.lookForOpponent()
    def ensureConnection(self):
        return self.session.ensureConnection()

class Grid:
    SHOTS_NOT_SHOTTED = 0
    SHOTS_HITTED = 1
    SHOTS_NOT_HITTED = 2
    SHOTS_BLOCKED = 3
    SHOTS_SHOTTED_UNKNOWN = 4

    def __init__(self):
        self.shipSizes: dict[int, int] = {1: 2, 2: 4, 3: 2, 4: 1} # shipSize : shipCount
        self.flyingShip: Ship = Ship([-1, -1], 0, True)
        self.placedShips: list[Ship] = []
        self.shottedMap =  [[self.SHOTS_NOT_SHOTTED] * Constants.GRID_WIDTH for y in range(Constants.GRID_HEIGHT)]
        self.wholeHittedShips: list[Ship] = []

    def shipsDicts(self):
        return [ship.asDict() for ship in self.placedShips]
    def allShipsPlaced(self):
            return not any(self.shipSizes.values()) 

    def rotateShip(self):
        self.flyingShip.horizontal = not self.flyingShip.horizontal
    def changeCursor(self, mousePos):
        clicked = self._getClickedShip(mousePos)
        initialSize = self.flyingShip.size
        if clicked:
            self.changeSize(+1, canBeSame=True, currSize=clicked.size)
        if not clicked or (self.flyingShip.size == initialSize):
            self.removeShipInCursor()
    def removeShipInCursor(self):
        self.flyingShip.size = 0

    def mouseClick(self, mousePos, rightClick: bool) -> bool:
        '''handles the mouse click
        @rightClick - the click is considered RMB click, otherwise LMB
        @return - if anything changed'''
        if self.flyingShip.size == 0 or rightClick:
            return self.pickUpShip(mousePos)
        else:
            return self.placeShip()
    def canPlaceShip(self, placed):
        gridRect = pygame.Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT)
        if not gridRect.contains(placed.getOccupiedRect()):
            return False
        for ship in self.placedShips:
            if placed.isColliding(ship):
                return False
        return True

    def placeShip(self) -> bool:
        placed = self.flyingShip.getPlacedShip()
        canPlace = self.canPlaceShip(placed)
        if canPlace:
            self.placedShips.append(placed)
            self.shipSizes[placed.size] -= 1
            self.changeSize(+1, canBeSame=True)
        return canPlace
    def autoplace(self):
        if self.shipSizes == {1: 2, 2: 4, 3: 2, 4: 1}:
            self.flyingShip.setSize(0)
            dicts = [{'pos': [3, 0], 'size': 2, 'horizontal': True, 'hitted': [False, False]}, {'pos': [4, 3], 'size': 2, 'horizontal': False, 'hitted': [False, False]}, {'pos': [5, 7], 'size': 3, 'horizontal': True, 'hitted': [False, False, False]}, {'pos': [1, 5], 'size': 4, 'horizontal': False, 'hitted': [False, False, False, False]}, {'pos': [8, 4], 'size': 1, 'horizontal': True, 'hitted': [False]}, {'pos': [6, 1], 'size': 1, 'horizontal': False, 'hitted': [False]}, {'pos': [5, 9], 'size': 2, 'horizontal': True, 'hitted': [False, False]}, {'pos': [1, 1], 'size': 2, 'horizontal': False, 'hitted': [False, False]}, {'pos': [9, 0], 'size': 3, 'horizontal': False, 'hitted': [False, False, False]}]
            for d in dicts:
                ship = Ship.fromDict(d)
                self.placedShips.append(ship)
                self.shipSizes[ship.size] -= 1
            assert self.allShipsPlaced(), 'autoplace is expected to place all ships'
        else:
            logging.warning('Couldn\'t autoplace ships, because shipSizes isn\'t as expected')

    def pickUpShip(self, mousePos) -> bool:
        ship = self._getClickedShip(mousePos)
        if ship:
            self.removeShipInCursor()
            self.flyingShip = ship.getFlying()
            self.placedShips.remove(ship)
            self.shipSizes[ship.size] += 1
        return bool(ship)
    def _getClickedShip(self, mousePos):
        for ship in self.placedShips:
            if ship.realRect.collidepoint(mousePos):
                return ship
        return None

    def _nextShipSize(self, startSize, increment):
        currSize = startSize + increment
        while currSize not in self.shipSizes:
            if currSize == startSize: break
            currSize += increment
            currSize = currSize % (max(self.shipSizes.keys()) + 1)
        return currSize
    def changeSize(self, increment: int, *, canBeSame=False, currSize=None):
        if currSize is None:
            currSize = self.flyingShip.size
        startSize = currSize
        if not canBeSame:
            currSize = self._nextShipSize(currSize, increment)
        while self.shipSizes[currSize] == 0:
            currSize = self._nextShipSize(currSize, increment)
            if currSize == startSize:
                if self.shipSizes[currSize] == 0:
                    self.removeShipInCursor()
                return
        self.flyingShip.setSize(currSize)
    
    def opponentShot(self, pos):
        for ship in self.placedShips:
            if ship.shot(pos):
                return True
        return False
    def shoot(self, mousePos):
        clickedX, clickedY = mousePos[0] // Constants.GRID_X_SPACING, mousePos[1] // Constants.GRID_Y_SPACING
        if self.shottedMap[clickedY][clickedX] != self.SHOTS_NOT_SHOTTED:
            return False
        self.shottedMap[clickedY][clickedX] = self.SHOTS_SHOTTED_UNKNOWN
        return [clickedX, clickedY]
    def updateHitted(self, pos, hitted, wholeShip):
        assert self.shottedMap[pos[1]][pos[0]] == self.SHOTS_SHOTTED_UNKNOWN
        self.shottedMap[pos[1]][pos[0]] = [self.SHOTS_NOT_HITTED, self.SHOTS_HITTED][hitted]
        if wholeShip:
            ship = Ship.fromDict(wholeShip)
            assert all(ship.hitted)
            self.wholeHittedShips.append(ship)
            self.markBlocked(ship)
    def markBlocked(self, ship):
            rect: pygame.Rect = ship.getnoShipsRect()
            rect = rect.clip(pygame.Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT))
            for x in range(rect.x, rect.x + rect.width):
                for y in range(rect.y, rect.y + rect.height):
                    if self.shottedMap[y][x] == self.SHOTS_NOT_SHOTTED:
                        self.shottedMap[y][x] = self.SHOTS_BLOCKED

    def drawGrid(self, window):
        self.drawGridlines(window)
        for ship in self.placedShips:
            ship.draw(window)
        if self.flyingShip.size:
            self.flyingShip.draw(window)
    def drawShotted(self, window):
        self.drawGridlines(window)
        for y, lineShotted in enumerate(self.shottedMap):
            for x, shotted in enumerate(lineShotted):
                pos = (x * Constants.GRID_X_SPACING + Constants.GRID_X_SPACING // 2, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_SPACING // 2)
                if shotted == self.SHOTS_HITTED:
                    pygame.draw.circle(window, (255, 0, 0), pos, Constants.GRID_X_SPACING // 4)
                elif shotted == self.SHOTS_NOT_HITTED:
                    pygame.draw.circle(window, (0, 0, 255), pos, Constants.GRID_X_SPACING // 4)
                elif shotted == self.SHOTS_BLOCKED:
                    pygame.draw.circle(window, (128, 128, 128), pos, Constants.GRID_X_SPACING // 4)

        for ship in self.wholeHittedShips:
            ship.drawWholeHitted(window)
        
    def drawGridlines(self, window):
        for row in range(Constants.GRID_HEIGHT):
            yCoord = Constants.GRID_Y_SPACING * row
            pygame.draw.line(window, (0, 0, 0), (0, yCoord), (Constants.SCREEN_WIDTH, yCoord))
        for col in range(Constants.GRID_WIDTH):
            xCoord = Constants.GRID_X_SPACING * col
            pygame.draw.line(window, (0, 0, 0), (xCoord, 0), (xCoord, Constants.SCREEN_HEIGHT))


class Ship:
    def __init__(self, pos: list, size, horizontal, hitted=None):
        self.pos: list[int] = pos
        self.size: int = size
        self.horizontal: bool = horizontal
        if hitted is None:
            hitted = [False] * size
        self.hitted: list[bool] = hitted
    
    def asDict(self):
        return {'pos': self.pos, 'size': self.size, 'horizontal': self.horizontal, 'hitted': self.hitted}
    @ classmethod
    def fromDict(self, d: dict):
        return Ship(d['pos'], d['size'], d['horizontal'], d['hitted'])
    
    def setSize(self, size):
        self.size = size
        self.hitted = [False] * size
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
    
    def shot(self, pos) -> bool:
        if not self.getOccupiedRect().collidepoint(pos):
            return False

        realPos = pos[0] * Constants.GRID_X_SPACING, pos[1] * Constants.GRID_Y_SPACING
        for i, (x, y) in enumerate(self.getRealSegmentCoords()):
            r = pygame.Rect(x, y, 1, 1)
            if r.collidepoint((realPos)):
                self.hitted[i] = True
                return True
        return False
    
    def draw(self, window):
        for hitted, (x, y) in zip(self.hitted, self.getRealSegmentCoords()):
            pygame.draw.rect(window, (0, 0, 0), (x, y, Constants.GRID_X_SPACING, Constants.GRID_Y_SPACING), 1)
            if hitted:
                pos = x + Constants.GRID_X_SPACING // 2, y + Constants.GRID_Y_SPACING // 2
                pygame.draw.circle(window, (255, 0, 0), pos, Constants.GRID_X_SPACING // 4)
        pygame.draw.rect(window, (0, 0, 0), self.realRect, 4)
    def drawWholeHitted(self, window):
        for (x, y) in self.getRealSegmentCoords():
            pos = x + Constants.GRID_X_SPACING // 2, y + Constants.GRID_Y_SPACING // 2
            pygame.draw.circle(window, (0, 0, 0), pos, Constants.GRID_X_SPACING // 8)
        
        pos = self.realPos
        start = pos[0] + Constants.GRID_X_SPACING // 2, pos[1] + Constants.GRID_Y_SPACING // 2
        end = pos[0] + (self.widthInGrid - 1) * Constants.GRID_X_SPACING + Constants.GRID_X_SPACING // 2, pos[1] + (self.heightInGrid - 1) * Constants.GRID_Y_SPACING + Constants.GRID_Y_SPACING // 2
        pygame.draw.line(window, (0, 0, 0), start, end, 3)