import logging, sys
from pygame import Rect, mouse
from . import Constants, Frontend
from .Session import Session
from Shared.Enums import SHOTS, STAGES, COM

class Game:
    def __init__(self):
        self.session = Session()
        self.grid = Grid()
        self.gameStage: STAGES = STAGES.CONNECTING
    def newGameStage(self, stage: STAGES):
        assert stage != self.gameStage
        self.gameStage = stage
        if self.gameStage in [STAGES.WON, STAGES.LOST, STAGES.CLOSING] and self.session.connected:
            self.session.disconnect()
        elif self.gameStage == STAGES.PLACING and '--autoplace' in sys.argv:
            self.grid.autoplace()
            self.toggleGameReady()
        self.drawStatic()

    # requests -------------------------------------------------
    def connectCallback(self, res):
        self.session.id = res['id']
        self.session.connected = True
        self.newGameStage(STAGES.PAIRING)
    def pairCallback(self, res):
        if res['paired']:
            self.newGameStage(STAGES.PLACING)
    def gameReadiness(self):
        assert self.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT]
        if self.session.alreadySent[COM.GAME_READINESS]: return
        state =  {'ships': self.grid.shipsDicts(), 'ready': self.gameStage != STAGES.GAME_WAIT}
        wasPlacing = self.gameStage == STAGES.PLACING
        lamda = lambda res: self.gameReadinessCallback(wasPlacing, res)
        if self.gameStage == STAGES.PLACING:
            self.newGameStage(STAGES.GAME_WAIT)
        self.session.tryToSend(COM.GAME_READINESS, state, lamda, blocking=False, mustSend=True)
    def gameReadinessCallback(self, wasPlacing, res):
        assert res['approved'] or not wasPlacing, 'transition from placing to wait should always be approved'
        if not wasPlacing and res['approved']:
            self.newGameStage(STAGES.PLACING)
    def gameWaitCallback(self, res):
        if res['started']:
            onTurn = res['on_turn'] == self.session.id
            self.newGameStage(STAGES.SHOOTING if onTurn else STAGES.GETTING_SHOT)
    def shootReq(self, gridPos):
        assert self.gameStage == STAGES.SHOOTING
        callback = lambda res: self.shootCallback(gridPos, res)
        self.session.tryToSend(COM.SHOOT, {'pos': gridPos}, callback, blocking=False, mustSend=True)
    def shootCallback(self, gridPos, res):
        hitted, wholeShip, gameWon = res['hitted'], res['whole_ship'], res['game_won']
        self.grid.updateHitted(gridPos, hitted, wholeShip)
        self.newGameStage(STAGES.WON if gameWon else STAGES.GETTING_SHOT)
    def gettingShotCallback(self, res):
        if res['shotted']:
            self.grid.opponentShot(res['pos'])
            self.newGameStage(STAGES.LOST if res['lost'] else STAGES.SHOOTING)
    
    def handleRequests(self):
        stayConnected = self.session.loadResponses()
        if self.gameStage in [STAGES.WON, STAGES.LOST, STAGES.CLOSING]:
            self.session.quit(must=(self.gameStage == STAGES.CLOSING))
            if self.gameStage == STAGES.CLOSING:
                Frontend.quit()
        elif not stayConnected:
            self.newGameStage(STAGES.WON)
            self.session.quit(must=False)
        elif self.gameStage == STAGES.CONNECTING:
            self.session.tryToSend(COM.CONNECT, {}, self.connectCallback, blocking=False)
        elif self.gameStage == STAGES.PAIRING:
            self.session.tryToSend(COM.PAIR, {}, self.pairCallback, blocking=True)
        elif self.gameStage == STAGES.GAME_WAIT:
            self.session.tryToSend(COM.GAME_WAIT, {}, self.gameWaitCallback, blocking=True)
        elif self.gameStage == STAGES.GETTING_SHOT:
            self.session.tryToSend(COM.OPPONENT_SHOT, {}, self.gettingShotCallback, blocking=True)
        self.session.spawnConnectionCheck()

    # controls and API -------------------------------------------------
    def rotateShip(self):
        if self.gameStage == STAGES.PLACING:
            self.grid.rotateShip()
    def changeCursor(self):
        if self.gameStage == STAGES.PLACING and not self.grid.allShipsPlaced():
            self.grid.changeCursor(mouse.get_pos())
    def mouseClick(self, mousePos, rightClick):
        if self.gameStage == STAGES.PLACING:
            changed = self.grid.mouseClick(mousePos, rightClick)
            if changed:
                self.toggleGameReady()
        elif self.gameStage == STAGES.SHOOTING and not rightClick:
            self.shoot(mousePos)
    def changeShipSize(self, increment: int):
        if self.gameStage == STAGES.PLACING and not self.grid.allShipsPlaced():
            self.grid.changeSize(increment)
    def shoot(self, mousePos):
        if self.gameStage == STAGES.SHOOTING:
            gridPos = self.grid.shoot(mousePos)
            if gridPos:
                self.shootReq(gridPos)
    def toggleGameReady(self):
        if self.grid.allShipsPlaced():
            logging.debug('toggling game readiness to ' + ('ready' if self.gameStage == STAGES.PLACING else 'waiting'))
            self.gameReadiness()
    # drawing --------------------------------
    def drawGame(self):
        if self.gameStage in [STAGES.PLACING, STAGES.SHOOTING, STAGES.GETTING_SHOT]:
            Frontend.fill((255, 255, 255))
        if self.gameStage == STAGES.PLACING:
            self.grid.drawPlaced()
            self.grid.drawFlying()
        elif self.gameStage == STAGES.SHOOTING:
            self.grid.drawShooting()
        elif self.gameStage == STAGES.GETTING_SHOT:
            self.grid.drawPlaced()
            self.grid.drawMineNotHitted()
        else:
            return
        Frontend.update()
    def drawStatic(self):
        Frontend.fill((255, 255, 255))
        if self.gameStage == STAGES.PAIRING:
            Frontend.render('ArialBig', (50, 300), 'Waiting for opponent...', (0, 0, 0))
        elif self.gameStage == STAGES.GAME_WAIT:
            self.grid.drawPlaced()
            Frontend.render('ArialMiddle', (25, 200), 'Waiting for the other player to place ships...', (0, 0, 0), 1, (255, 255, 255), 5, (0, 0, 0), 2)
        elif self.gameStage in [STAGES.WON, STAGES.LOST]:
            message = ['You lost!   :(', 'You won!   :)'][self.gameStage == STAGES.WON]
            Frontend.render('ArialBig', (150, 300), message, (0, 0, 0))
            Frontend.render('ArialSmall', (150, 400), 'Press any key for exit', (0, 0, 0))
        Frontend.update()

class Grid:
    def __init__(self):
        self.shipSizes: dict[int, int] = {1: 2, 2: 4, 3: 2, 4: 1} # shipSize : shipCount
        self.flyingShip: Ship = Ship([-1, -1], 0, True)
        self.placedShips: list[Ship] = []
        self.shottedMap =  [[SHOTS.NOT_SHOTTED] * Constants.GRID_WIDTH for y in range(Constants.GRID_HEIGHT)]
        self.wholeHittedShips: list[Ship] = []
        self.mineNotHitted = [[SHOTS.NOT_SHOTTED] * Constants.GRID_WIDTH for y in range(Constants.GRID_HEIGHT)]

    def shipsDicts(self):
        return [ship.asDict() for ship in self.placedShips]
    def allShipsPlaced(self):  # TODO: excuse me wth
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
        gridRect = Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT)
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
        self.mineNotHitted[pos[1]][pos[0]] = SHOTS.NOT_HITTED
        return False
    def shoot(self, mousePos):
        clickedX, clickedY = mousePos[0] // Constants.GRID_X_SPACING, mousePos[1] // Constants.GRID_Y_SPACING
        if self.shottedMap[clickedY][clickedX] != SHOTS.NOT_SHOTTED:
            return False
        self.shottedMap[clickedY][clickedX] = SHOTS.SHOTTED_UNKNOWN
        return [clickedX, clickedY]
    def updateHitted(self, pos, hitted, wholeShip):
        assert self.shottedMap[pos[1]][pos[0]] == SHOTS.SHOTTED_UNKNOWN
        self.shottedMap[pos[1]][pos[0]] = [SHOTS.NOT_HITTED, SHOTS.HITTED][hitted]
        if wholeShip:
            ship = Ship.fromDict(wholeShip)
            assert all(ship.hitted)
            self.wholeHittedShips.append(ship)
            self.markBlocked(ship)
    def markBlocked(self, ship):
            rect: Rect = ship.getnoShipsRect()
            rect = rect.clip(Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT))
            for x in range(rect.x, rect.x + rect.width):
                for y in range(rect.y, rect.y + rect.height):
                    if self.shottedMap[y][x] == SHOTS.NOT_SHOTTED:
                        self.shottedMap[y][x] = SHOTS.BLOCKED
    
    def drawPlaced(self):
        self._drawGridlines()
        for ship in self.placedShips:
            ship.draw()
    def drawMineNotHitted(self):
        for y, row in enumerate(self.mineNotHitted):
            for x, col in enumerate(row):
                if col == SHOTS.NOT_HITTED:
                    pos = (x * Constants.GRID_X_SPACING + Constants.GRID_X_SPACING // 2, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_SPACING // 2)
                    Frontend.draw.circle((0, 0, 255), pos, Constants.GRID_X_SPACING // 4)
    def drawFlying(self):
        if self.flyingShip.size:
            self.flyingShip.draw()
    def drawShooting(self):
        self._drawGridlines()
        for y, lineShotted in enumerate(self.shottedMap):
            for x, shotted in enumerate(lineShotted):
                pos = (x * Constants.GRID_X_SPACING + Constants.GRID_X_SPACING // 2, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_SPACING // 2)
                if shotted == SHOTS.HITTED:
                    Frontend.draw.circle((255, 0, 0), pos, Constants.GRID_X_SPACING // 4)
                elif shotted == SHOTS.NOT_HITTED:
                    Frontend.draw.circle((0, 0, 255), pos, Constants.GRID_X_SPACING // 4)
                elif shotted == SHOTS.BLOCKED:
                    Frontend.draw.circle((128, 128, 128), pos, Constants.GRID_X_SPACING // 4)

        for ship in self.wholeHittedShips:
            ship.draw()
        
    def _drawGridlines(self):
        for row in range(Constants.GRID_HEIGHT):
            yCoord = Constants.GRID_Y_SPACING * row
            Frontend.draw.line((0, 0, 0), (0, yCoord), (Constants.SCREEN_WIDTH, yCoord), 1)
        for col in range(Constants.GRID_WIDTH):
            xCoord = Constants.GRID_X_SPACING * col
            Frontend.draw.line((0, 0, 0), (xCoord, 0), (xCoord, Constants.SCREEN_HEIGHT), 1)


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
    def realPos(self) -> list[int]:
        if self.pos == [-1, -1]:
            mouseX, mouseY = mouse.get_pos()
            return [mouseX - self.widthInGrid * Constants.GRID_X_SPACING // 2, mouseY - self.heightInGrid * Constants.GRID_Y_SPACING // 2]
        else:
            return [self.pos[0] * Constants.GRID_X_SPACING, self.pos[1] * Constants.GRID_Y_SPACING]
    @ property
    def realRect(self):
        '''Rect of real ship coordinates'''
        return Rect(*self.realPos, self.widthInGrid * Constants.GRID_X_SPACING, self.heightInGrid * Constants.GRID_Y_SPACING)
    
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
        return Rect(self.pos[0] - 1, self.pos[1] - 1,  self.widthInGrid + 2, self.heightInGrid + 2)
    def getOccupiedRect(self):
        return Rect(self.pos[0], self.pos[1], self.widthInGrid, self.heightInGrid)
    def isColliding(self, other):
        '''checks if other collides with the noShipsRect of self'''
        return self.getnoShipsRect().colliderect(other.getOccupiedRect())
    
    def shot(self, pos) -> bool:
        if not self.getOccupiedRect().collidepoint(pos):
            return False

        realPos = pos[0] * Constants.GRID_X_SPACING, pos[1] * Constants.GRID_Y_SPACING
        for i, (x, y) in enumerate(self.getRealSegmentCoords()):
            r = Rect(x, y, 1, 1)
            if r.collidepoint((realPos)):
                self.hitted[i] = True
                return True
        return False
    
    def draw(self):
        allHitted = all(self.hitted)
        lastPos = self.realPos
        lastPos[0] += Constants.GRID_X_SPACING // 2
        lastPos[1] += Constants.GRID_Y_SPACING // 2
        for hitted, (x, y) in zip(self.hitted, self.getRealSegmentCoords()):
            Frontend.draw.rect((0, 0, 0), (x, y, Constants.GRID_X_SPACING, Constants.GRID_Y_SPACING), 1)
            if hitted:
                pos = x + Constants.GRID_X_SPACING // 2, y + Constants.GRID_Y_SPACING // 2
                Frontend.draw.circle((255, 0, 0), pos, Constants.GRID_X_SPACING // 4)
                if allHitted:
                    Frontend.draw.circle((0, 0, 0), pos, Constants.GRID_X_SPACING // 8)
                    Frontend.draw.line((0, 0, 0), lastPos, pos, 3)
                    lastPos = pos
        Frontend.draw.rect((0, 0, 0), self.realRect, 4)
            