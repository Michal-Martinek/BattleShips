import logging, sys, string
from pygame import Rect, mouse
import pygame
from typing import TypeVar, Optional

from . import Constants
from . import Frontend
from .Session import Session
from Shared.Enums import SHOTS, STAGES, COM

class Game:
	def __init__(self):
		self.session = Session()
		self.options = Options()
		self.redrawNeeded = True
		self.repeatableInit()
		if '--autoplay' in sys.argv or '--autoplay-repeat' in sys.argv:
			self.newGameStage(STAGES.CONNECTING)
	def repeatableInit(self):
		self.grid = Grid(True)
		self.opponentGrid = Grid(False)
		self.gameStage: STAGES = STAGES.MAIN_MENU
		self.options.repeatableInit()
	def quit(self):
		logging.info('Closing due to client quit')
		self.newGameStage(STAGES.CLOSING)
	def newGameStage(self, stage: STAGES):
		assert STAGES.COUNT == 12
		assert stage != self.gameStage
		self.gameStage = stage
		Frontend.readyBtnRect = None
		if self.gameStage == STAGES.MAIN_MENU:
			self.repeatableInit()
		elif self.gameStage in [STAGES.WON, STAGES.LOST, STAGES.CLOSING] and self.session.connected:
			self.session.disconnect()
			if self.gameStage != STAGES.CLOSING and '--autoplay' in sys.argv:
				pygame.time.set_timer(pygame.QUIT, 1000, 1)
		elif self.gameStage == STAGES.PLACING:
			self.redrawHUD()
			if '--autoplace' in sys.argv:
				self.grid.autoplace()
				self.toggleGameReady()
		elif self.gameStage in [STAGES.GAME_WAIT, STAGES.SHOOTING, STAGES.GETTING_SHOT]:
			self.redrawHUD()
		logging.debug(f'New game stage: {str(stage)}')
		self.redrawNeeded = True

	# requests -------------------------------------------------
	def connectCallback(self, res):
		self.session.id = res['id']
		self.session.connected = True
		logging.info(f'Connected to server as {self.session.id}')
		self.newGameStage(STAGES.PAIRING)
	def pairCallback(self, res):
		if res['paired']:
			logging.info(f"Paired with {res['opponent']['id']} - '{res['opponent']['name']}', starting placing stage")
			self.options.opponentName = res['opponent']['name']
			self.newGameStage(STAGES.PLACING)
	def opponentReadyCallback(self, res):
		self.options.opponentReady = res['opponent_ready']
		self.redrawHUD()
	def gameReadiness(self):
		assert self.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT]
		if self.session.alreadySent[COM.GAME_READINESS]: return
		wasPlacing = self.gameStage == STAGES.PLACING
		if wasPlacing: self.newGameStage(STAGES.GAME_WAIT)
		state = {'ships': self.grid.shipsDicts(), 'ready': wasPlacing}
		lamda = lambda res: self.gameReadinessCallback(wasPlacing, res)
		self.session.tryToSend(COM.GAME_READINESS, state, lamda, blocking=False, mustSend=True)
	def gameReadinessCallback(self, wasPlacing, res):
		assert res['approved'] or not wasPlacing, 'transition from placing to wait should always be approved'
		self.options.opponentReady = res['opponent_ready']
		if not wasPlacing and res['approved']:
			self.newGameStage(STAGES.PLACING)
		else: self.redrawHUD()
	def gameWaitCallback(self, res):
		if res['started']:
			onTurn = res['on_turn'] == self.session.id
			self.grid.initShipSizes()
			self.newGameStage(STAGES.SHOOTING if onTurn else STAGES.GETTING_SHOT)
			logging.info('Shooting started')
	def shootReq(self, gridPos):
		assert self.gameStage == STAGES.SHOOTING
		callback = lambda res: self.shootCallback(gridPos, res)
		self.session.tryToSend(COM.SHOOT, {'pos': gridPos}, callback, blocking=False, mustSend=True)
	def shootCallback(self, gridPos, res):
		hitted, sunkenShip, gameWon = res['hitted'], Ship.fromDict(res['sunken_ship']), res['game_won']
		self.opponentGrid.gotShotted(gridPos, hitted, sunkenShip)
		self.newGameStage(STAGES.WON if gameWon else STAGES.GETTING_SHOT)
		if gameWon: logging.info('Game won')
	def gettingShotCallback(self, res):
		if not res['shotted']: return
		self.grid.gotShotted(res['pos'])
		self.newGameStage(STAGES.LOST if res['lost'] else STAGES.SHOOTING)
		if res['lost']: logging.info('Game lost')

	def handleRequests(self):
		assert STAGES.COUNT == 12
		stayConnected = self.session.loadResponses()
		if self.gameStage in [STAGES.MAIN_MENU, STAGES.MULTIPLAYER_MENU, STAGES.WON, STAGES.LOST]:
			if '--autoplay-repeat' in sys.argv and not self.session.connected and not any(self.session.alreadySent.values()):
				logging.debug('Autoplay repeat')
				self.newGameStage(STAGES.CONNECTING)
			return
		elif self.gameStage == STAGES.CLOSING:
			self.session.quit()
		elif not stayConnected:
			logging.warning('Server commanded disconnect')
			self.newGameStage(STAGES.WON)
		
		elif self.gameStage == STAGES.CONNECTING:
			self.session.tryToSend(COM.CONNECT, {'name': self.options.submittedPlayerName()}, self.connectCallback, blocking=False)
		elif self.gameStage == STAGES.PAIRING:
			self.session.tryToSend(COM.PAIR, {}, self.pairCallback, blocking=True)
		elif self.gameStage == STAGES.PLACING:
			self.session.tryToSend(COM.OPPONENT_READY, {'expected': self.options.opponentReady}, self.opponentReadyCallback, blocking=True)
		elif self.gameStage == STAGES.GAME_WAIT:
			self.session.tryToSend(COM.GAME_WAIT, {}, self.gameWaitCallback, blocking=True)
		elif self.gameStage == STAGES.GETTING_SHOT:
			self.session.tryToSend(COM.OPPONENT_SHOT, {}, self.gettingShotCallback, blocking=True)
		self.session.spawnConnectionCheck()

	# controls and API -------------------------------------------------
	def rotateShip(self):
		if self.gameStage == STAGES.PLACING:
			self.grid.rotateShip()
			self.redrawNeeded = True
	def changeCursor(self):
		if self.gameStage == STAGES.PLACING and not self.grid.allShipsPlaced():
			self.grid.changeCursor(mouse.get_pos())
			self.redrawNeeded = True
	def mouseClick(self, mousePos, rightClick=False):
		if rightClick and self.gameStage != STAGES.PLACING: return
		if mousePos[1] <= Constants.HUD_RECT.bottom: self.grid.removeShipInCursor()
		self.redrawNeeded = True
		if Constants.HEADER_CLOSE_RECT.collidepoint(mousePos):
			self.quit()
		elif Constants.HEADER_MINIMIZE_RECT.collidepoint(mousePos):
			pygame.display.iconify()
		elif Frontend.grabWindow(mousePos):
			self.options.inputActive = False
		elif self.gameStage == STAGES.MULTIPLAYER_MENU: self.options.mouseClick(mousePos)
		elif not rightClick and Frontend.readyBtnRect and Frontend.readyBtnRect.collidepoint(mousePos):
			self.toggleGameReady()
		elif self.gameStage == STAGES.PLACING:
			changed = self.grid.mouseClick(mousePos, rightClick)
			if changed: self.redrawHUD()
		elif self.gameStage == STAGES.SHOOTING:
			self.shoot(mousePos)
	def mouseMovement(self, event):
		if Frontend.windowGrabbedPos: Frontend.moveWindow(event.pos)
		elif Frontend.HUDCollide(event.pos): self.redrawHUD()
		elif Frontend.headerBtnCollide(event.pos) or self.grid.flyingShip.size: self.redrawNeeded = True
	def keydownInMenu(self, event):
		self.redrawNeeded = True
		if event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
			if self.options.inputActive: self.options.inputActive = False
			else: self.newGameStage(STAGES.MULTIPLAYER_MENU if self.gameStage == STAGES.MAIN_MENU else STAGES.CONNECTING)
		elif event.key in [pygame.K_LEFT, pygame.K_RIGHT]:
			self.options.moveCursor([-1, 1][event.key == pygame.K_RIGHT])
		elif event.key in [pygame.K_BACKSPACE, pygame.K_DELETE]:
			self.options.removeChar(event.key == pygame.K_DELETE)
		else:
			self.options.addChar(event.unicode)
	def changeShipSize(self, increment: int):
		if self.gameStage == STAGES.PLACING and not self.grid.allShipsPlaced():
			self.grid.changeSize(increment)
			self.redrawNeeded = True
	def advanceAnimations(self):
		if self.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT, STAGES.SHOOTING, STAGES.GETTING_SHOT]:
			self.redrawNeeded |= pygame.display.get_active()
			Ship.advanceAnimations()
	def shoot(self, mousePos):
		if self.gameStage == STAGES.SHOOTING:
			gridPos = self.opponentGrid.shoot(mousePos)
			if gridPos:
				self.shootReq(gridPos)
	def toggleGameReady(self):
		if self.gameStage in [STAGES.PLACING, STAGES.GAME_WAIT] and self.grid.allShipsPlaced():
			logging.info('toggling game readiness to ' + ('ready' if self.gameStage == STAGES.PLACING else 'waiting'))
			self.gameReadiness()
	# drawing --------------------------------
	def drawGame(self):
		assert STAGES.COUNT == 12
		if not self.redrawNeeded or self.gameStage == STAGES.CLOSING: return
		self.redrawNeeded = False
		drawHud = True
		if self.gameStage == STAGES.PLACING:
			self.grid.draw(flying=True)
		elif self.gameStage == STAGES.GAME_WAIT:
			self.grid.draw()
			Frontend.render(Frontend.FONT_ARIAL_MIDDLE, (25, 200), 'Waiting for the other player to place ships...', (0, 0, 0), (255, 255, 255), (0, 0, 0), 5, 5)
		elif self.gameStage == STAGES.SHOOTING:
			self.opponentGrid.draw(shots=True)
		elif self.gameStage == STAGES.GETTING_SHOT:
			self.grid.draw(shots=True)
		else:
			drawHud = False
			self.drawStatic()
		Frontend.drawHeader()
		if drawHud: Frontend.drawHUD()
		Frontend.update()
	def drawStatic(self):
		assert STAGES.COUNT == 12
		Frontend.fillColor((255, 255, 255))
		if self.gameStage == STAGES.MAIN_MENU:
			Frontend.render(Frontend.FONT_ARIAL_BIG, (150, 300), 'MAIN MENU')
			Frontend.render(Frontend.FONT_ARIAL_SMALL, (150, 400), 'Press ENTER to play multiplayer')
		elif self.gameStage == STAGES.MULTIPLAYER_MENU:
			Frontend.render(Frontend.FONT_ARIAL_BIG, (150, 150), 'MULTIPLAYER')
			Frontend.render(Frontend.FONT_ARIAL_MIDDLE, (150, 250), 'Input your name')
			Frontend.render(Frontend.FONT_ARIAL_MIDDLE, Constants.MULTIPLAYER_INPUT_BOX, self.options.showedPlayerName(), (0, 0, 0), (255, 255, 255) if self.options.inputActive else (128, 128, 128), (0, 0, 0), 3, 8)
			Frontend.render(Frontend.FONT_ARIAL_SMALL, (150, 450), 'Press ENTER to play...')
		elif self.gameStage == STAGES.PAIRING:
			Frontend.render(Frontend.FONT_ARIAL_BIG, (50, 300), 'Waiting for opponent...')
		elif self.gameStage in [STAGES.WON, STAGES.LOST]:
			message = ['You lost!   :(', 'You won!   :)'][self.gameStage == STAGES.WON]
			Frontend.render(Frontend.FONT_ARIAL_BIG, (150, 300), message, (0, 0, 0))
			Frontend.render(Frontend.FONT_ARIAL_SMALL, (150, 400), 'Press any key for exit')
	def redrawHUD(self):
		grid = self.opponentGrid if self.gameStage == STAGES.SHOOTING else self.grid
		Frontend.genHUD(self.options, grid.shipSizes, self.gameStage)
		self.redrawNeeded = True

class Options:
	'''Class responsible for loading, holding and storing client side options,
		such as settings and stored data'''
	MAX_LEN = 19
	def __init__(self):
		self.playerName: list[str] = []
		self.repeatableInit()
	def repeatableInit(self):
		self.cursor:int = len(self.playerName) # points before char
		self.inputActive = False
		self.opponentName = ''
		self.opponentReady = False

	def addChar(self, c):
		if c == ' ': c = '_'
		if c and (c in string.ascii_letters or c in string.digits or c in '!#*+-_'):
			if self.inputActive:
				if len(self.playerName) < Options.MAX_LEN:
					self.playerName.insert(self.cursor, c)
					self.cursor += 1
	def removeChar(self, delAfter=False):
		if (self.cursor <= 0 and not delAfter) or (self.cursor == len(self.playerName) and delAfter): return
		if self.inputActive and len(self.playerName):
			if not delAfter: self.cursor -= 1
			self.playerName.pop(self.cursor)
	def moveCursor(self, off):
		if 0 <= self.cursor + off <= len(self.playerName):
			self.cursor += off
	def mouseClick(self, mousePos) -> bool:
		if Constants.MULTIPLAYER_INPUT_BOX.collidepoint(mousePos) ^ self.inputActive:
			self.inputActive ^= True
			self.cursor = len(self.playerName)
			return True
	def showedPlayerName(self) -> str:
		if not self.playerName and not self.inputActive: return 'Name'
		s = ''.join(self.playerName)
		if self.inputActive: s = s[:self.cursor] + '|' + s[self.cursor:]
		return s
	def submittedPlayerName(self) -> str:
		if not self.playerName: return 'Noname'
		return ''.join(self.playerName)

Ship = TypeVar('Ship')
class Grid:
	def __init__(self, isLocal: bool):
		self.isLocal = isLocal
		self.initShipSizes()
		self.flyingShip: Ship = Ship([-1, -1], 0, True)
		self.ships: list[Ship] = []
		self.shots = [[SHOTS.NOT_SHOTTED] * Constants.GRID_WIDTH for y in range(Constants.GRID_HEIGHT)]
	def initShipSizes(self):
		self.shipSizes: dict[int, int] = {1: 2, 2: 4, 3: 2, 4: 1} # shipSize : shipCount

	def shipsDicts(self):
		return [ship.asDict() for ship in self.ships]
	def allShipsPlaced(self):
			return not any(self.shipSizes.values())

	# interface ---------------------------------------------
	def rotateShip(self): # TODO: maybe the one-ship shouldn't be turned?
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
		for ship in self.ships:
			if placed.isColliding(ship):
				return False
		return True

	def placeShip(self) -> bool:
		placed = self.flyingShip.getPlacedShip()
		canPlace = self.canPlaceShip(placed)
		if canPlace:
			self.ships.append(placed)
			self.shipSizes[placed.size] -= 1
			self.changeSize(+1, canBeSame=True)
		return canPlace
	def autoplace(self):
		if self.shipSizes == {1: 2, 2: 4, 3: 2, 4: 1}:
			self.flyingShip.setSize(0)
			dicts = [{'pos': [3, 0], 'size': 2, 'horizontal': True, 'hitted': [False, False]}, {'pos': [4, 3], 'size': 2, 'horizontal': False, 'hitted': [False, False]}, {'pos': [5, 7], 'size': 3, 'horizontal': True, 'hitted': [False, False, False]}, {'pos': [1, 5], 'size': 4, 'horizontal': False, 'hitted': [False, False, False, False]}, {'pos': [8, 4], 'size': 1, 'horizontal': True, 'hitted': [False]}, {'pos': [6, 1], 'size': 1, 'horizontal': False, 'hitted': [False]}, {'pos': [5, 9], 'size': 2, 'horizontal': True, 'hitted': [False, False]}, {'pos': [1, 1], 'size': 2, 'horizontal': False, 'hitted': [False, False]}, {'pos': [9, 0], 'size': 3, 'horizontal': False, 'hitted': [False, False, False]}]
			for d in dicts:
				ship = Ship.fromDict(d)
				self.ships.append(ship)
				self.shipSizes[ship.size] -= 1
			assert self.allShipsPlaced(), 'autoplace is expected to place all ships'

	def pickUpShip(self, mousePos) -> bool:
		ship = self._getClickedShip(mousePos)
		if ship:
			self.removeShipInCursor()
			self.flyingShip = ship.getFlying()
			self.ships.remove(ship)
			self.shipSizes[ship.size] += 1
		return bool(ship)
	def _getClickedShip(self, mousePos):
		for ship in self.ships:
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

	# shooting --------------------------------------------------
	def localGridShotted(self, pos) -> tuple[bool, Ship]:
		'''returns if hitted , any hitted ship'''
		for ship in self.ships:
			if ship.shot(pos):
				return True, ship
		return False, None
	def gotShotted(self, pos, hitted=False, sunkenShip=None):
		'''process shot result, supplied from server for opponents grid'''
		if self.isLocal: hitted, sunkenShip = self.localGridShotted(pos)
		else: assert self.shots[pos[1]][pos[0]] == SHOTS.SHOTTED_UNKNOWN
		self.shots[pos[1]][pos[0]] = [SHOTS.NOT_HITTED, SHOTS.HITTED][hitted]
		if sunkenShip and all(sunkenShip.hitted):
			if not self.isLocal: self.ships.append(sunkenShip)
			self.shipSizes[sunkenShip.size] -= 1
			self._markBlocked(sunkenShip)
	def shoot(self, mousePos) -> Optional[list[int]]:
		'''mouse click -> clicked grid pos if shooting location available'''
		clickedX, clickedY = mousePos[0] // Constants.GRID_X_SPACING, (mousePos[1] - Constants.GRID_Y_OFFSET) // Constants.GRID_Y_SPACING
		if self.shots[clickedY][clickedX] != SHOTS.NOT_SHOTTED: return None
		self.shots[clickedY][clickedX] = SHOTS.SHOTTED_UNKNOWN
		if self.isLocal: self.gotShotted((clickedX, clickedY))
		return [clickedX, clickedY]
	def _markBlocked(self, ship: Ship):
		'''marks squares around sunken ship'''
		rect: Rect = ship.getnoShipsRect()
		occupied: Rect = ship.getOccupiedRect()
		for x in range(rect.x, rect.x + rect.width):
			for y in range(rect.y, rect.y + rect.height):
				if self.shots[y][x] == SHOTS.NOT_SHOTTED:
					self.shots[y][x] = SHOTS.BLOCKED
				if occupied.collidepoint((x, y)):
					self.shots[y][x] = SHOTS.HITTED_SUNKEN

	# drawing -----------------------------------------------
	def drawShot(self, color, x, y):
		pos = (x * Constants.GRID_X_SPACING + Constants.GRID_X_SPACING // 2, y * Constants.GRID_Y_SPACING + Constants.GRID_Y_SPACING // 2 + Constants.GRID_Y_OFFSET)
		Frontend.drawCircle(color, pos, Constants.GRID_X_SPACING // 4)
	def drawShots(self):
		colors = {SHOTS.HITTED: (255, 0, 0), SHOTS.NOT_HITTED: (11, 243, 255), SHOTS.BLOCKED: (128, 128, 128)}
		for y, lineShotted in enumerate(self.shots):
			for x, shot in enumerate(lineShotted):
				if shot in colors and (not self.isLocal or shot == SHOTS.NOT_HITTED):
					self.drawShot(colors[shot], x, y)
	def draw(self, *, flying=False, shots=False):
		Frontend.drawBackground()
		for ship in self.ships: ship.draw()
		if shots: self.drawShots()
		if flying and self.flyingShip.size: self.flyingShip.draw()


class Ship:
	animationStage = 0 # 0 - 2
	animationDirection = True
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
		if d is None: return None
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
		'''return real pos wrt grid'''
		if self.pos == [-1, -1]:
			mouseX, mouseY = mouse.get_pos()
			return [mouseX - self.widthInGrid * Constants.GRID_X_SPACING // 2, mouseY - Constants.GRID_Y_OFFSET - self.heightInGrid * Constants.GRID_Y_SPACING // 2]
		else:
			return [self.pos[0] * Constants.GRID_X_SPACING, self.pos[1] * Constants.GRID_Y_SPACING]
	@ property
	def realRect(self):
		'''Rect of window ship coordinates'''
		return Rect(self.realPos[0], self.realPos[1] + Constants.GRID_Y_OFFSET, self.widthInGrid * Constants.GRID_X_SPACING, self.heightInGrid * Constants.GRID_Y_SPACING)

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
		rect = Rect(self.pos[0] - 1, self.pos[1] - 1,  self.widthInGrid + 2, self.heightInGrid + 2)
		return rect.clip(Rect(0, 0, Constants.GRID_WIDTH, Constants.GRID_HEIGHT))
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
	@ classmethod
	def advanceAnimations(cls):
		cls.animationStage += cls.animationDirection * 2 - 1
		if cls.animationStage == 0:
			cls.animationDirection = True
		elif cls.animationStage == 2:
			cls.animationDirection = False
	def draw(self):
		img = Frontend.getFrame(self.size, self.horizontal, self.hitted, self.animationStage)
		rect = img.get_rect()
		rect.center = self.realRect.center
		Frontend.blit(img, rect)
