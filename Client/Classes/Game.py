import pygame
from . import Constants

class Game:
    def __init__(self):
        self.gridObj = Grid()

    def mouseClick(self):
        if self.gridObj.shipInCursor:
            self.gridObj.placeShip()
        else:
            self.gridObj.pickUpShip()

    def drawGame(self, window):
        self.gridObj.drawGrid(window)
    def moveCurrShipType(self):
        self.gridObj.moveCurrShipType()
    def rotateFlyingShip(self):
        self.gridObj.rotateFlyingShip()
    def removeShipInCursor(self):
        self.gridObj.removeShipInCursor()


class Grid:
    def __init__(self):
        self.shipTypes = [[1, 2], [2, 4], [3, 2], [4, 1]]
        self.currentShipTypeIndex = 0
        self.ships = []
        self.shipInCursor = Ship(1, 1)
        self.setFlyingShip()
        
        # self.opponentShotted = [[False for x in range(GraphicsConstants.GRID_WIDTH)] for y in range(GraphicsConstants.GRID_HEIGHT)]
        # self.playerShotted = [[False for x in range(GraphicsConstants.GRID_WIDTH)] for y in range(GraphicsConstants.GRID_HEIGHT)]
        # self.occupiedSpots = [[False for x in range(GraphicsConstants.GRID_WIDTH)] for y in range(GraphicsConstants.GRID_HEIGHT)]
        # ships (objects), occupied spots, numbers of alive ships, shotted spaces from the oppponent and current player
    # def handleShots(self, x, y):
    #     pass
    def getShipsForSending(self) -> list:
        data = []
        for ship in self.ships:
            data.append( [ship.col, ship.row ,ship.orientation, ship.length] )
        return data
    def rotateFlyingShip(self):
        if self.shipInCursor:
            self.shipInCursor.rotate()
    def canPlaceShip(self):
        potentiallyPlacedShip = self.shipInCursor.getPlacedShip()
        for ship in self.ships:
            if potentiallyPlacedShip.isColliding(ship):
                return False
        gridRect = pygame.Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT)
        if gridRect.contains(potentiallyPlacedShip.getOccupiedRect()):
            return potentiallyPlacedShip

    def placeShip(self):
        '''called when self.shipInCursor is not None'''
        if placedShip := self.canPlaceShip():                
            self.ships.append(placedShip)
            self.updateShipTypesAfterPlace()
    def pickUpShip(self):
        '''called when self.shipInCursor is None and clicked'''
        mouseX, mouseY = pygame.mouse.get_pos()
        col = mouseY // Constants.GRID_Y_SPACING
        row = mouseX // Constants.GRID_X_SPACING

        for ship in self.ships:
            if ship.realRect.collidepoint((mouseX, mouseY)):
                self.pickUpClickedShip(ship)
                break
    def pickUpClickedShip(self, ship):
        self.shipInCursor = ship.getFlyingShip()
        self.ships.remove(ship)
        for i, shipType in enumerate(self.shipTypes):
            if shipType[0] == ship.length:
                shipType[1] += 1
                self.currentShipTypeIndex = i
                break

    def removeShipInCursor(self):
        self.shipInCursor = None
    def updateShipTypesAfterPlace(self):
        self.shipTypes[self.currentShipTypeIndex][1] -= 1
        if self.shipCount == 0:
            self.moveCurrShipType()
        self.setFlyingShip()
    def incrementShipTypeIndex(self):
        self.currentShipTypeIndex = (self.currentShipTypeIndex + 1) % len(self.shipTypes)
    def moveCurrShipType(self):
        if self.shipInCursor is None:
            return self.setFlyingShip()
        startingIndex = self.currentShipTypeIndex
        self.incrementShipTypeIndex()
        while self.shipCount == 0:
            if self.currentShipTypeIndex == startingIndex:
                raise ValueError('No more ships to place')
            self.incrementShipTypeIndex()
        self.setFlyingShip()
    
    @ property
    def shipType(self):
        return self.shipTypes[self.currentShipTypeIndex][0]
    @ property
    def shipCount(self):
        return self.shipTypes[self.currentShipTypeIndex][1]

    def setFlyingShip(self):
        orientation = 0 if self.shipInCursor is None else self.shipInCursor.orientation
        self.shipInCursor = FlyingShip(orientation, self.shipType)

    def drawGrid(self, window):
        if self.shipInCursor:
            self.shipInCursor.draw(window)
        for ship in self.ships:
            ship.draw(window)
        self.drawGridlines(window)

    def drawGridlines(self, window):
        for row in range(Constants.GRID_HEIGHT):
            yCoord = Constants.GRID_Y_SPACING * row
            pygame.draw.line(window, (0, 0, 0), (0, yCoord), (Constants.SCREEN_WIDTH, yCoord))
        for col in range(Constants.GRID_WIDTH):
            xCoord = Constants.GRID_X_SPACING * col
            pygame.draw.line(window, (0, 0, 0), (xCoord, 0), (xCoord, Constants.SCREEN_HEIGHT))




class Ship:
    def __init__(self, orientation, length):
        '''orientation: 0 - horizontal, 1 - vertical'''
        # ship type, x, y, length, orientation, places it occupies?, sunken spots
        self.orientation = orientation
        self.length = length

    @ property
    def heightInGrid(self):
        return (self.length - 1) * self.orientation + 1
    @ property
    def widthInGrid(self):
        return (self.length - 1) * (self.orientation == 0) + 1
    @ property
    def realHeightInGrid(self):
        return self.heightInGrid * Constants.GRID_Y_SPACING
    @ property
    def realWidthInGrid(self):
        return self.widthInGrid * Constants.GRID_X_SPACING
    @ property
    def realRect(self):
        '''Rect of real ship coordinates'''
        realY, realX = self.realPos
        return pygame.Rect(realX, realY, self.realWidthInGrid, self.realHeightInGrid)
    
    # def shot(x, y):
    #     pass
    # def place():
    #     pass
    # def __eq__(self, other):
    #     return self.orientation == other.orientation and self.length == other.length
    # def __hash__(self):
    #     return hash(self.__dict__)
    def getRealSegmentCoords(self):
        '''returns list of real coords of all ship segments'''
        segments = []
        realY, realX = self.realPos
        for dy in range(self.heightInGrid):
            for dx in range(self.widthInGrid):
                y = realY + dy * Constants.GRID_Y_SPACING
                x = realX + dx * Constants.GRID_X_SPACING
                segments.append([y, x])
        return segments
    
    def draw(self, window):
        for x, y in self.getRealSegmentCoords():
            self.drawShipSegment(window, x, y)
        pygame.draw.rect(window, (0, 0, 0), self.realRect, 4)
    def drawShipSegment(self, window, y, x):
        pygame.draw.rect(window, (0, 0, 0), (x, y, Constants.GRID_X_SPACING, Constants.GRID_Y_SPACING), 1)
    

class PlacedShip(Ship):
    def __init__(self, col, row, orientation, length):
        self.col = col
        self.row = row
        super().__init__(orientation, length)
    
    @ property
    def realPos(self):
        return self.col * Constants.GRID_Y_SPACING, self.row * Constants.GRID_X_SPACING

    def getFlyingShip(self):
        return FlyingShip(self.orientation, self.length)
    
    def getOccupiedSpots(self):
        spots = []
        for y in range(self.heightInGrid):
            for x in range(self.widthInGrid):
                spots.append( [self.col + y, self.row + x] )
        return spots
    
    def getnoShipsRect(self):
        return pygame.Rect(self.row - 1, self.col - 1, self.widthInGrid + 2, self.heightInGrid + 2)
    def getOccupiedRect(self):
        return pygame.Rect(self.row, self.col, self.widthInGrid, self.heightInGrid)
    def isColliding(self, other):
        '''checks if other collides with the noShipsRect of self'''
        return self.getnoShipsRect().colliderect(other.getOccupiedRect())




class FlyingShip(Ship):
    def __init__(self, orientation, length):
        '''x and y offsets - how many pixels from the top-left edge to the mouse location'''
        super().__init__(orientation, length)
        self.setOffsets()
    
    @ property
    def realPos(self):
        mouseX, mouseY = pygame.mouse.get_pos()
        return mouseY - self.yOffset, mouseX - self.xOffset
    

    def getPlacedShip(self):
        realY, realX = self.realPos
        col = realY // Constants.GRID_Y_SPACING
        col += (realY % Constants.GRID_Y_SPACING) > (Constants.GRID_Y_SPACING // 2)
        row = realX // Constants.GRID_X_SPACING
        row += (realX % Constants.GRID_X_SPACING) > (Constants.GRID_X_SPACING // 2)
        return PlacedShip(col, row, self.orientation, self.length)
    
    def rotate(self):
        self.orientation = 1 - self.orientation
        self.setOffsets()
    def setOffsets(self):
        self.yOffset = self.realHeightInGrid // 2
        self.xOffset = self.realWidthInGrid // 2
