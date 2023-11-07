import socket
import logging, inspect
import threading, queue
import random, time, os

from dataclasses import dataclass
from typing import Union, Optional

from Shared import ConnectionPrimitives
from Shared.Enums import STAGES, COM
from Shared.Helpers import runFuncLogged, initLogging

# globals ----------------------------------------
MAX_TIME_FOR_DISCONNECT = 30.
MAX_TIME_FOR_BLOCKING = 20.

class ConnectedPlayer:
    def __init__(self, id: int):
        self.connected: bool = True
        self.id: int = id
        self.inGame = False
        self.gameId: int = 0
        self.lastReqTime = time.time()
        self.gameState: dict = {'ready': False}
    def __repr__(self):
        return f'{self.__class__.__name__}(id={self.id}, gameId={self.gameId}, gameState={self.gameState})'
    def shootingReady(self):
        return self.gameState['ready']
    def disconnect(self):
        logging.info(f'disconnecting player {self.id}')
        self.connected = False
@ dataclass
class Request:
    conn: socket.socket
    playerId: int
    command: COM
    payload: dict
    stayConnected: bool = True
@ dataclass
class BlockingRequest:
    req: Request
    player: ConnectedPlayer
    timeRecvd: float
    defaultResponse: dict
    @ property
    def command(self):
        return self.req.command
    @ property
    def stayConnected(self):
        return self.req.stayConnected
    @ stayConnected.setter
    def stayConnected(self, val):
        self.req.stayConnected = val

# error helpers -------------------------------------------
class FailedAsertionError(AssertionError):
    '''Signalizes failed assertion to communicate the need to ignore the req'''
    pass
def sendErrorResponse(req: Request, error: str, obj=None): # NOTE doesn't accept BlockingRequest
    obj = '' if obj is None else str(obj)
    payload = {'error': error, 'error_obj': obj, 'stay_connected': False}
    ConnectionPrimitives.send(req.conn, req.playerId, COM.ERROR, payload)
    req.conn.close()
def asert(cond, req, msg, obj=None):
    if cond: return
    caller = inspect.getframeinfo(inspect.stack()[1][0])
    log = f"{msg}: '{obj}'" if obj is not None else msg
    logging.error(f"{os.path.basename(caller.filename)}:{caller.lineno} ASSERTION FAILED: ID{req.playerId} {log}")
    sendErrorResponse(req, msg, obj)
    raise FailedAsertionError(log)

# impl classes ----------------------------------------------------------
class Game:
    def __init__(self, id, player1: ConnectedPlayer, player2: ConnectedPlayer, bothPaired: bool):
        self.id: int = id
        self.gameActive: bool = True
        self.gameStage: int = STAGES.PLACING if bothPaired else STAGES.PAIRING
        self.players: dict[int, ConnectedPlayer] = {player1.id: player1, player2.id: player2}
        self.setPlayersForGame()
        self.playerOnTurn: int = 0
        self.shottedPos = [-1, -1]
    def setPlayersForGame(self):
        for p in self.players.values():
            p.inGame = True
            p.gameId = self.id

    def updateGameState(self, player: ConnectedPlayer, state):
        # TODO: validation of the game state?
        player.gameState = state
    def getOpponentState(self, player):
        return self.getOpponent(player).gameState

    def getOpponent(self, player: ConnectedPlayer) -> ConnectedPlayer:
        return [p for p in self.players.values() if p.id != player.id][0]
    def swapTurn(self):
        l = list(self.players.keys())
        l.remove(self.playerOnTurn)
        self.playerOnTurn = l[0]
        self.shottedPos = [-1, -1]

    def canBeEnded(self):
        return not (self.gameActive or any([p.connected for p in self.players.values()]))
    def playerDisconnect(self, player: ConnectedPlayer):
        player.disconnect()
        self.gameActive = False
    def gameReadiness(self, player: ConnectedPlayer, payload: dict) -> bool:
        '''returns if the request was approved'''
        if payload['ready'] or self.gameStage == STAGES.PLACING:
            self.updateGameState(player, payload)
            if self.canStartShooting():
                self.startShooting()
            return True
        return False
    def canStartShooting(self):
        return self.gameStage == STAGES.PLACING and all([p.shootingReady() for p in self.players.values()])
    def startShooting(self):
        logging.info(f'starting shooting game id {self.id}')
        self.gameStage = STAGES.SHOOTING
        self.playerOnTurn = random.choice(list(self.players.keys()))
    def opponentShottedReq(self, player: ConnectedPlayer) -> tuple[bool, list[int], bool]:
        '''request called when responding to COM.OPPONENT_SHOT
        @return (list[int] - where opponent shotted, bool - if you lost'''
        pos = self.shottedPos
        self.swapTurn()
        return pos, self.gameStage == STAGES.WON
    def didOpponentShoot(self, player) -> bool:
        return self.shottedPos != [-1, -1] and player.id != self.playerOnTurn
    def shoot(self, player, pos) -> tuple[bool, dict, bool]:
        '''@player - player who shotted
        @pos - (x, y) pos where did he shoot
        @return (bool - hitted, dict - whole ship hitted if any, bool - game won)'''
        self.shottedPos = pos
        for ship in self.getOpponentState(player)['ships']:
            x, y = ship['pos']
            horizontal = ship['horizontal']
            size = ship['size']
            if (x <= pos[0] <= x + (size - 1) * horizontal) and (y <= pos[1] <= y + (size - 1) * (not horizontal)):
                hittedSpot = (pos[0] - x) if horizontal else (pos[1] - y)
                ship['hitted'][hittedSpot] = True
                wholeShip = ship if all(ship['hitted']) else None
                gameWon = all([all(ship['hitted']) for ship in self.getOpponentState(player)['ships']])
                return True, wholeShip, gameWon
        return False, None, False


class Server:
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.settimeout(1.0)
        self.serverSocket.listen()

        self.players: dict[int, ConnectedPlayer] = dict()
        self.games: dict[int, Game] = dict()

        self.waitingReqs: queue.Queue[Request] = queue.Queue()
        self.blockingReqs: dict[int, BlockingRequest] = {}
        self.closeEvent = threading.Event()

        self.acceptThread = threading.Thread(target=lambda: runFuncLogged(self.acceptLoop), daemon=True, name='Thread-Accept')
        self.acceptThread.start()
        self.waitingReqsThread = threading.Thread(target=lambda: runFuncLogged(self.waitingReqsHandler), daemon=True, name='Thread-WaitingReqs')
        self.waitingReqsThread.start()
    def close(self, closeNow=False):
        self.closeEvent.set()
        if not closeNow:
            self.acceptThread.join()
            self.waitingReqsThread.join()
        self.serverSocket.close()

    def unknownIdReq(self, req: Request):
        if req.command == COM.CONNECT:
            player = self.newConnectedPlayer()
            self.players[player.id] = player
            logging.info(f'connecting new player from {req.conn.getpeername()} as {player.id}')
            req.playerId = player.id
            self._sendResponse(req, {'id': player.id})
        else:
            asert(False, req, 'unknown player id', req.playerId)

    def dispatchRequest(self, req: Request):
        if req.playerId in self.players:        
            player = self.players[req.playerId]
            player.lastReqTime = time.time()
        self.waitingReqs.put(req)
    
    def acceptLoop(self):
        while not self.closeEvent.is_set() or self.players:
            try:
                conn, addr = self.serverSocket.accept()
                req = self._recvReq(conn)
                self.dispatchRequest(req)           
            except socket.timeout:
                pass
            finally:
                self.checkConnections()
                self.checkGames()
            
    
    def checkGames(self):
        for game in list(self.games.values()):
            if game.canBeEnded():
                self.endGame(game)

    def waitingReqsHandler(self):
        while not self.closeEvent.is_set() or self.players or self.blockingReqs:
            try:
                req  = self.waitingReqs.get(timeout=1.)
                self.handleIncomingReq(req)
            except queue.Empty:
                pass
            except FailedAsertionError:
                pass
            finally:
                self.checkWaitingReqs()
    def handleIncomingReq(self, req: Request):
        if req.playerId not in self.players:
            return self.unknownIdReq(req)
        
        player = self.players[req.playerId]
        asert(player.connected, req, 'player marked as disconnected')
        if player.id in self.blockingReqs:
            logging.debug(f'Responding with default due to another req from {player.id}')
            self.respondBlockingReq(player, useDefault=True)
        
        if req.command == COM.DISCONNECT:
            req.stayConnected = False
            self._sendResponse(req)
            self.disconnectPlayer(player)
        elif req.command == COM.PAIR:
            self.pairPlayer(player, req)
        elif req.command == COM.CONNECTION_CHECK:
            self.addBlockingReq(player, req, {})
        else:
            asert(player.gameId in self.games, req, 'unknown game id', player.gameId)
            game = self.games[player.gameId]
            req.stayConnected = game.gameActive

            if req.command == COM.GAME_READINESS:
                self.handleGameReadiness(player, game, req)
            elif req.command == COM.GAME_WAIT:
                self.handleGameWait(player, game, req)
            elif req.command == COM.SHOOT:
                # NOTE: when the player on turn shoot before the other player makes COM.OPPONENT_SHOT this will crash, because the game.swapOnTurn() didn't yet happen 
                self.shootReq(player, game, req)
            elif req.command == COM.OPPONENT_SHOT:
                self.opponentShotted(player, game, req)
            else:
                asert(False, req, 'unknown command', req.command)

    def checkConnections(self):
        for player in list(self.players.values()):
            if time.time() - player.lastReqTime > MAX_TIME_FOR_DISCONNECT:
                if player.connected:
                    logging.warning(f'disconnecting player {player.id} due to not receiving requests')
                    self.disconnectPlayer(player)
    
    def disconnectPlayer(self, player: ConnectedPlayer):
        if player.inGame:
            game = self.games[player.gameId]
            game.playerDisconnect(player)
        else:
            if player.id in self.blockingReqs:
                self.blockingReqs[player.id].req.stayConnected = False
                self.respondBlockingReq(player, {})
            player.disconnect()
            self.removePlayer(player)
    def removePlayer(self, player: ConnectedPlayer):
        assert player.id in self.players and not player.connected
        self.players.pop(player.id)
    def removeGame(self, game: Game):
        assert game.id in self.games and game.canBeEnded()
        self.games.pop(game.id)
    def endGame(self, game: Game):
        logging.info(f'ending game id {game.id}')
        for p in game.players.values():
            self.removePlayer(p)
        self.removeGame(game)


    def addBlockingReq(self, player: ConnectedPlayer, req: Request, defaultResponse: dict):
        '''adds to blockingReqs for player, the defaults are sent back if the request times out or the same player sends another req'''
        assert player.id not in self.blockingReqs, 'only one blocking req per player'
        logging.debug(f'adding blocking request {req.command}')
        self.blockingReqs[player.id] = BlockingRequest(req, player, time.time(), defaultResponse)
    def respondBlockingReq(self, player: ConnectedPlayer, payload: dict={}, *, useDefault=False):
        '''sends response for blocking req for this player
        , if 'useDefault' it sends the default response in the 'BlockingRequest', 
        otherwise it sends supplied response'''
        req = self.blockingReqs.pop(player.id)
        self._sendResponse(req, req.defaultResponse if useDefault else payload)

    def _isPlayerPairableWith(self, player: ConnectedPlayer, possibleOpponent: ConnectedPlayer):
        return not possibleOpponent.inGame and possibleOpponent.id != player.id
    def findOpponent(self, player: ConnectedPlayer) -> Optional[ConnectedPlayer]:
        for req in self.blockingReqs.values(): # primarily try to find a opponent from the waiting reqs
            if req.req.command == COM.PAIR and self._isPlayerPairableWith(player, req.player):
                return req.player
        possible = list(filter(lambda p: self._isPlayerPairableWith(player, p), self.players.values()))
        if len(possible) == 0: return None
        opponent = possible[0]
        if opponent.id in self.blockingReqs: assert self.blockingReqs[opponent.id].req.command == COM.PAIR, 'if the opponent _isPairableWith then any blocking req must be a COM.PAIR'
        return opponent
    def pairPlayer(self, player: ConnectedPlayer, req: Request):
        if player.inGame:
            game = self.games[player.gameId]
            asert(game.gameStage == STAGES.PAIRING, req, 'Unexpected game stage for !PAIR', game.id)
            game.gameStage = STAGES.PLACING
            return self._sendResponse(req, {'paired': True}) # TODO report opponent id
        opponent = self.findOpponent(player)
        if opponent is None:
            self.addBlockingReq(player, req, {'paired': False})
        else:
            bothPaired = False
            if opponent.id in self.blockingReqs:
                self.respondBlockingReq(opponent, {'paired': True})
                bothPaired = True
            self.addNewGame(player, opponent, bothPaired)
            self._sendResponse(req, {'paired': True})
    def handleGameReadiness(self, player: ConnectedPlayer, game: Game, req: Request):
        approved = game.gameReadiness(player, req.payload)
        self._sendResponse(req, {'approved': approved})
        if game.gameStage == STAGES.SHOOTING:
            opponent = game.getOpponent(player)
            if opponent.id in self.blockingReqs:
                assert self.blockingReqs[opponent.id].command == COM.GAME_WAIT
                self.respondBlockingReq(opponent, {'started': True, 'on_turn': game.playerOnTurn})
    def handleGameWait(self, player: ConnectedPlayer, game: Game, req: Request):
        asert(player.shootingReady(), req, 'Unexpected !GAME_WAIT from unready player', player.id)
        if game.gameStage == STAGES.SHOOTING:
            self._sendResponse(req, {'started': True, 'on_turn': game.playerOnTurn})
        else:
            self.addBlockingReq(player, req, {'started': False})
    def shootReq(self, player: ConnectedPlayer, game: Game, req: Request):
        asert(player.id == game.playerOnTurn, req, 'only player on turn can shoot')
        hitted, wholeShip, gameWon = game.shoot(player, req.payload['pos'])
        if gameWon:
            game.gameStage = STAGES.WON
            req.stayConnected = False
            logging.info(f'Game {game.id} won {player.id}')
        opponent = game.getOpponent(player)
        if opponent.id in self.blockingReqs:
            blocking = self.blockingReqs[opponent.id]
            assert blocking.command == COM.OPPONENT_SHOT
            self.sendOpponentShottedRes(opponent, game, blocking)    
        self._sendResponse(req, {'hitted': hitted, 'whole_ship': wholeShip, 'game_won': gameWon})
    def opponentShotted(self, player: ConnectedPlayer, game: Game, req: Request):
        if game.didOpponentShoot(player):
            self.sendOpponentShottedRes(player, game, req)
        else:
            self.addBlockingReq(player, req, {'shotted': False})
    def sendOpponentShottedRes(self, player: ConnectedPlayer, game: Game, req):
        pos, lost = game.opponentShottedReq(player)
        payload = {'shotted': True, 'pos': pos, 'lost': lost}
        if lost:
            req.stayConnected = False
        if isinstance(req, Request):
            self._sendResponse(req, payload)
        else:
            assert isinstance(req, BlockingRequest) and player.id in self.blockingReqs
            self.respondBlockingReq(player, payload)
    def checkWaitingReqs(self):
        for req in list(self.blockingReqs.values()):
            if time.time() - req.timeRecvd > MAX_TIME_FOR_BLOCKING or self.closeEvent.is_set():
                self.respondBlockingReq(req.player, useDefault=True)
            elif req.player.inGame:
                game = self.games[req.player.gameId]
                if not game.gameActive:
                    req.stayConnected = False
                    self.respondBlockingReq(req.player, useDefault=True)

    def newConnectedPlayer(self):
        id = self._generateNewID(self.players)
        return ConnectedPlayer(id)
    def addNewGame(self, player1, player2, bothPaired: bool):
        id = self._generateNewID(self.games)
        game = Game(id, player1, player2, bothPaired)
        self.games[id] = game
        logging.info(f'starting new game id {id}, players: {player1.id}, {player2.id}')
    def _generateNewID(self, dictOfIds):
        bounds = (1000, 2**20)
        id = random.randint(*bounds)
        while id in dictOfIds:
            id = random.randint(*bounds)
        return id

    def _recvReq(self, conn: socket.socket) -> Request:
        id, command, payload = ConnectionPrimitives.recv(conn)
        req = Request(conn, id, command, payload)
        return req
    def _sendResponse(self, req: Union[Request, BlockingRequest], payload: dict={}):
        if isinstance(req, BlockingRequest):
            req = req.req
        payload.update({'stay_connected': req.stayConnected and not self.closeEvent.is_set()})
        assert req.playerId != 0
        ConnectionPrimitives.send(req.conn, req.playerId, req.command, payload)
        req.conn.close()


def serverMain():
    initLogging('server_log.txt')
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    logging.info(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')

    closeNow = False
    try:
        while server.acceptThread.is_alive() and server.waitingReqsThread.is_alive():
            time.sleep(3)
    except KeyboardInterrupt:
        print('Keyboard-Interrupt')
    else:
        closeNow = True
        logging.error('Thread died, alive threads: ' + ', '.join(map(str, threading.enumerate())))
    finally:
        server.close(closeNow)
def main():
    runFuncLogged(serverMain)
if __name__ == '__main__':
    main()
