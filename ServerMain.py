import socket, random, time, logging
from dataclasses import dataclass
from Shared import ConnectionPrimitives
from Shared.Enums import STAGES, COM

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

class Game:
    def __init__(self, id, player1: ConnectedPlayer, player2: ConnectedPlayer):
        self.id: int = id
        self.gameActive: bool = True
        self.gameStage: int = STAGES.PAIRING
        self.players: dict[int, ConnectedPlayer] = {player1.id: player1, player2.id: player2}
        self.setPlayersForGame()
        self.playerOnTurn: int = 0
        self.shottedPos = [-1, -1]

        self.pendingRequests: list[Request] = []
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
    def canStartShooting(self):
        return self.gameStage == STAGES.PLACING and all([p.shootingReady() for p in self.players.values()])
    def startShooting(self):
        assert self.gameStage == STAGES.PLACING, 'Game needs to be in the placing stage to start shooting'
        logging.info(f'starting shooting game id {self.id}')
        self.gameStage = STAGES.SHOOTING
        self.playerOnTurn = random.choice(list(self.players.keys()))
    def opponentShotted(self, player: ConnectedPlayer) -> tuple[bool, list[int], bool]:
        '''@return (bool - opponent shotted already, list[int] - where opponent shotted, bool - if you lost'''
        shotted = self.shottedPos != [-1, -1] and player.id != self.playerOnTurn
        pos = self.shottedPos
        lost = self.gameStage == STAGES.WON
        if shotted:
            self.swapTurn()
        if lost:
            self.gameActive = False
        return shotted, pos, lost
    def shoot(self, player, pos) -> tuple[bool, dict, bool]:
        '''@player - player who shotted
        @pos - (x, y) pos where did he shoot
        @return (bool - hitted, dict - whole ship hitted if any, bool - game won)'''
        assert player.id == self.playerOnTurn, 'only player on turn can shoot'
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
    def gameWon(self):
        self.gameStage = STAGES.WON

    def putReq(self, req: Request):
        self.pendingRequests.append(req)
    
    def handleRequests(self):
        for req in self.pendingRequests:
            player = self.players[req.playerId]
            self.handleRequest(player, req)
        self.pendingRequests.clear()
    
    def handleRequest(self, player: ConnectedPlayer, req: Request):
        '''handles queries from players who should be in a game
        @return True if the command was recognized'''
        if req.command == COM.CONNECTION_CHECK:
            self._sendResponse(req)
        elif req.command == COM.DISCONNECT:
            self.playerDisconnect(player)
            self._sendResponse(req)
        elif req.command == COM.PAIR:
            assert self.gameStage == STAGES.PAIRING
            logging.info(f'paired {player.id} with {self.getOpponent(player).id}')
            self.gameStage = STAGES.PLACING
            self._sendResponse(req, {'paired': True})
        elif req.command == COM.GAME_READINESS:
            approved = False
            if req.payload['ready'] or self.gameStage == STAGES.PLACING:
                self.updateGameState(player, req.payload)
                approved = True
            self._sendResponse(req, {'approved': approved})
        elif req.command == COM.GAME_WAIT:
            assert player.shootingReady(), 'Don\'t expect a COM.GAME_WAIT from player without being ready'
            if self.canStartShooting():
                self.startShooting()
            self._sendResponse(req, {'started': self.gameStage == STAGES.SHOOTING, 'on_turn': self.playerOnTurn})
        elif req.command == COM.SHOOT:
            # NOTE: when the player on turn shoot before the other player makes COM.OPPONENT_SHOT this will crash, because the game.swapOnTurn() didn't yet happen 
            hitted, wholeShip, gameWon = self.shoot(player, req.payload['pos'])
            if gameWon:
                self.gameWon()
            self._sendResponse(req, {'hitted': hitted, 'whole_ship': wholeShip, 'game_won': gameWon})
        elif req.command == COM.OPPONENT_SHOT:
            shotted, pos, lost = self.opponentShotted(player)
            self._sendResponse(req, {'shotted': shotted, 'pos': pos, 'lost': lost})
        else:
            assert False, f'unreachable: probably invalid command: "{req.command}"'
        return True
    
    def _sendResponse(self, req: Request, payload: dict={}):
        payload.update({'stay_connected': self.gameActive})
        ConnectionPrimitives.send(req.conn, req.playerId, req.command, payload)


class Server:
    MAX_TIME_FOR_DISCONNECT = 15.
    def __init__(self, addr):
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.bind(addr)
        self.serverSocket.settimeout(1.0)
        self.serverSocket.listen()

        self.players: dict[int, ConnectedPlayer] = dict()
        self.games: dict[int, Game] = dict()

        self.outGameReqs: list[tuple[ConnectedPlayer, Request]] = []

    # errors ---------------------------- # TODO: spawn errors
    def unknownPlayerError(self, req):
        logging.warning('unknown player, ignoring')
        self.sendErrorResponse(req, 'unknown_id')
    def sendErrorResponse(self, req, errorType):
        self._sendResponse(req, {'error_type': errorType}, command=COM.ERROR, stayConnected=False)
    # -----------------------------------

    def unknownIdReq(self, req: Request):
        if req.command == COM.CONNECT:
            player = self.newConnectedPlayer()
            assert player.id not in self.players
            self.players[player.id] = player
            logging.info(f'connecting new player from {req.conn.getpeername()}')
            self._sendResponse(req, {'id': player.id})
        else:
            self.unknownPlayerError(req)        

    def handleRequest(self, req: Request):
        if req.playerId not in self.players:
            self.unknownIdReq(req)
        else:
            player = self.players[req.playerId]
            player.lastReqTime = time.time()
            
            if not player.inGame:
                self.outGameReqs.append((player, req))
            else:
                assert player.gameId in self.games
                game = self.games[player.gameId]
                game.putReq(req)
    
    def loop(self):
        while True:
            try:
                conn, addr = self.serverSocket.accept()
                req = self._recvReq(conn)
                self.handleRequest(req)           
            except socket.timeout:
                pass
            finally:
                self.handleGames()
                self.handleOutGameReqs()
                self.checkConnections()
    
    def handleGames(self):
        for game in list(self.games.values()):
            game.handleRequests()
            if game.canBeEnded():
                self.endGame(game)

    def handleOutGameReqs(self):
        for player, req in self.outGameReqs:
            if req.command == COM.DISCONNECT:
                self.disconnectPlayer(player)
                self._sendResponse(req, stayConnected=False)
            elif req.command == COM.PAIR:
                self.pairPlayer(player, req)
            elif req.command == COM.CONNECTION_CHECK:
                self._sendResponse(req)
            else:
                assert False, 'unknown command, probably'
        self.outGameReqs.clear()
    

    def checkConnections(self):
        for player in list(self.players.values()):
            if time.time() - player.lastReqTime > self.MAX_TIME_FOR_DISCONNECT:
                if player.connected:
                    self.disconnectPlayer(player)
    
    def disconnectPlayer(self, player: ConnectedPlayer):
        if player.inGame:
            game = self.games[player.gameId]
            game.playerDisconnect(player)
        else:
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

    def _pairablePlayers(self, player: ConnectedPlayer):
        return list(filter(lambda p: not p.inGame and p.id != player.id, self.players.values()))
    def pairPlayer(self, player: ConnectedPlayer, req: Request):
        pairable = self._pairablePlayers(player)
        if len(pairable) > 0:
            opponent = pairable[0]
            self.addNewGame(player, opponent)
        self._sendResponse(req, {'paired': player.inGame})

    def newConnectedPlayer(self):
        id = self._generateNewID(self.players)
        return ConnectedPlayer(id)
    def addNewGame(self, player1, player2):
        id = self._generateNewID(self.games)
        game = Game(id, player1, player2)
        assert id not in self.games
        self.games[game.id] = game
        return game
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
    def _sendResponse(self, req: Request, payload: dict={}, command=None, stayConnected=True):
        if command is None:
            command = req.command
        payload.update({'stay_connected': stayConnected})
        ConnectionPrimitives.send(req.conn, req.playerId, command, payload)


def serverMain():
    logging.basicConfig(level=logging.INFO)
    ADDR = (socket.gethostbyname(socket.gethostname()), 1250)
    server = Server(ADDR)
    logging.info(f'server ready and listening at {ADDR[0]}:{ADDR[1]}')
    server.loop()    
if __name__ == '__main__':
    serverMain()
