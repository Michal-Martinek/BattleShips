import pygame
from . import Constants

class Grid:
    def __init__(self):
        self.shipSizes: dict[int, int] = {1: 2, 2: 4, 3: 2, 4: 1} # shipSIze : shipCount
        self.flyingShip: Ship = Ship([-1, -1], 1, True)
        self.placedShips: list[Ship] = []

    def rotateShip(self):
        self.flyingShip.horizontal = not self.flyingShip.horizontal
    def removeShipInCursor(self):
        self.flyingShip.size = 0

    def mouseClick(self, mousePos):
        if self.flyingShip.size == 0:
            self.pickUpShip(mousePos)
        else:
            self.placeShip(mousePos)
    def canPlaceShip(self, placed):
        gridRect = pygame.Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT)
        if not gridRect.contains(placed.getOccupiedRect()):
            return False
        for ship in self.placedShips:
            if placed.isColliding(ship):
                return False
        return True

    def placeShip(self, mousePos):
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

    def _nextShipSize(self, currSize, increment):
        currSize += increment
        while currSize not in self.shipSizes:
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
